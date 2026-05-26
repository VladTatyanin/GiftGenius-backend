import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import uuid

from db.database import DatabaseManager, init_db, close_db
from rag.chain import get_rag_chain, clear_memory

app = FastAPI(title="GiftGenius API", version="1.0.0")

# CORS для Android
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class GenerateResponse(BaseModel):
    success: bool
    answer: str
    params: Dict
    session_id: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str

class FavoriteRequest(BaseModel):
    name: str
    description: Optional[str] = None
    price: int = 0
    interests: Optional[str] = None
    recipient: Optional[str] = None
    occasion: Optional[str] = None


class FavoriteResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: int
    created_at: str


class SearchHistoryResponse(BaseModel):
    id: int
    question: str
    recipient: Optional[str]
    occasion: Optional[str]
    interests: Optional[str]
    budget_min: Optional[int]
    budget_max: Optional[int]
    created_at: str


sessions = {}

def get_or_create_session(session_id: str = None) -> str:
    """Получить существующую или создать новую сессию"""
    if session_id and session_id in sessions:
        return session_id

    new_session_id = session_id or str(uuid.uuid4())
    sessions[new_session_id] = {
        "created_at": datetime.now(),
        "chain": get_rag_chain(session_id=new_session_id, temperature=0.85)
    }
    return new_session_id


def get_chain(session_id: str):
    """Получить цепочку для сессии"""
    if session_id not in sessions:
        sessions[session_id] = {
            "created_at": datetime.now(),
            "chain": get_rag_chain(session_id=session_id, temperature=0.85)
        }
    return sessions[session_id]["chain"]

@app.on_event("startup")
async def startup():
    await init_db()
    print("PostgreSQL database started")

@app.on_event("shutdown")
async def shutdown():
    await close_db()
    print("PostgreSQL database stopped")

@app.get("/", response_model=HealthResponse)
async def root():
    """Проверка работоспособности API"""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )

@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Генерация идей подарков

    Пример запроса:
    {
        "question": "что подарить маме на день рождения 5000 рублей",
        "session_id": "user_123"
    }
    """

    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    try:
        # Получаем или создаем сессию
        session_id = get_or_create_session(request.session_id)
        chain = get_chain(session_id)

        # Получаем или создаем пользователя в БД
        user = await DatabaseManager.get_or_create_user(session_id)

        # Генерируем идеи
        result = await chain.generate_gift_ideas(request.question)

        interests_value = result["params"].get("interests", [])
        if isinstance(interests_value, list):
            interests_value = ', '.join(interests_value)

        # Сохраняем историю поиска в БД
        await DatabaseManager.save_search(
            user_id=user.id,
            search_data={
                "question": request.question,
                "recipient": result["params"].get("recipient"),
                "occasion": result["params"].get("occasion"),
                "interests": interests_value,
                "budget_min": result["params"].get("budget_min"),
                "budget_max": result["params"].get("budget_max"),
            },
            answer=result["answer"]
        )

        return GenerateResponse(
            success=True,
            answer=result["answer"],
            params=result["params"],
            session_id=result["session_id"],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/favorite/{session_id}")
async def add_favorite(session_id: str, request: FavoriteRequest):
    """Добавить подарок в избранное"""
    try:
        user = await DatabaseManager.get_or_create_user(session_id)

        # Проверяем, нет ли уже такого подарка в избранном
        if await DatabaseManager.is_favorite(user.id, request.name):
            return {"success": False, "message": "Подарок уже в избранном"}

        gift = await DatabaseManager.add_favorite(user.id, {
            "name": request.name,
            "description": request.description,
            "price": request.price,
            "interests": request.interests,
            "recipient": request.recipient,
            "occasion": request.occasion
        })

        return {
            "success": True,
            "message": "Подарок добавлен в избранное",
            "favorite_id": gift.id
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/favorites/{session_id}")
async def get_favorites(session_id: str):
    """Получить все избранные подарки пользователя"""
    try:
        user = await DatabaseManager.get_or_create_user(session_id)
        favorites = await DatabaseManager.get_favorites(user.id)

        return {
            "success": True,
            "favorites": [
                {
                    "id": f.id,
                    "name": f.name,
                    "description": f.description,
                    "price": f.price,
                    "interests": f.interests,
                    "recipient": f.recipient,
                    "occasion": f.occasion,
                    "created_at": f.created_at.isoformat() if hasattr(f, 'created_at') else None
                }
                for f in favorites
            ]
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/favorite/{session_id}/{gift_id}")
async def remove_favorite(session_id: str, gift_id: int):
    """Удалить подарок из избранного"""
    try:
        user = await DatabaseManager.get_or_create_user(session_id)
        await DatabaseManager.remove_favorite(gift_id, user.id)

        return {
            "success": True,
            "message": "Подарок удален из избранного"
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{session_id}")
async def get_search_history(session_id: str):
    """Получить историю поиска пользователя"""
    try:
        user = await DatabaseManager.get_or_create_user(session_id)
        history = await DatabaseManager.get_search_history(user.id)

        return {
            "success": True,
            "history": [
                {
                    "id": h.id,
                    "question": h.question,
                    "recipient": h.recipient,
                    "occasion": h.occasion,
                    "interests": h.interests,
                    "budget_min": h.budget_min,
                    "budget_max": h.budget_max,
                    "created_at": h.created_at.isoformat() if hasattr(h, 'created_at') else None
                }
                for h in history
            ]
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/history/{session_id}")
async def clear_search_history(session_id: str):
    """Очистить историю поиска пользователя"""
    try:
        user = await DatabaseManager.get_or_create_user(session_id)
        await DatabaseManager.clear_search_history(user.id)

        return {
            "success": True,
            "message": "История поиска очищена",
            "session_id": session_id
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Получить информацию о сессии"""
    if session_id in sessions:
        return {
            "exists": True,
            "session_id": session_id,
            "created_at": sessions[session_id]["created_at"].isoformat()
        }
    return {"exists": False, "session_id": session_id}


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Удалить сессию"""
    if session_id in sessions:
        chain = sessions[session_id]["chain"]
        chain.clear_memory()
        del sessions[session_id]
        return {"success": True, "message": "Session deleted"}
    return {"success": False, "message": "Session not found"}

@app.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Очистить историю поиска пользователя"""
    try:
        user = await DatabaseManager.get_or_create_user(session_id)
        await DatabaseManager.clear_search_history(user.id)
        return {"success": True, "message": "History cleared", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Статистика по сессиям"""
    return {
        "active_sessions": len(sessions),
        "total_requests": sum(len(s["chain"].memory.messages) for s in sessions.values())
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)