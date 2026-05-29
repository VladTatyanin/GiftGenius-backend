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

@app.get("/stats")
async def get_stats():
    """Статистика по сессиям"""
    return {
        "active_sessions": len(sessions),
        "total_requests": sum(len(s["chain"].memory.messages) for s in sessions.values())
    }

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(app, host="127.0.0.1", port=port)