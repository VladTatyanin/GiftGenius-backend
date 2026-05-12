from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import uuid

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


class ClearRequest(BaseModel):
    session_id: str

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

@app.get("/", response_model=HealthResponse)
async def root():
    """Проверка работоспособности API"""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check для мониторинга"""
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

        # Генерируем идеи
        result = await chain.generate_gift_ideas(request.question)

        return GenerateResponse(
            success=True,
            answer=result["answer"],
            params=result["params"],
            session_id=result["session_id"],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear")
async def clear(request: ClearRequest):
    """
    Очистка истории диалога для сессии
    """
    try:
        if request.session_id in sessions:
            chain = sessions[request.session_id]["chain"]
            chain.clear_memory()
            return {"success": True, "message": "History cleared", "session_id": request.session_id}
        else:
            return {"success": True, "message": "Session not found", "session_id": request.session_id}
    except Exception as e:
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