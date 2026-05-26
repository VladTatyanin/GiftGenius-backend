import uuid

from sqlalchemy import Column, String, Integer, ForeignKey, Text, Boolean, select, desc, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "postgresql+asyncpg://giftgenius:giftgenius123@localhost:5432/giftgenius"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(100), unique=True, nullable=True)
    username = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=True)

class Gift(Base):
    __tablename__ = "gifts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))

    # Информация о подарке
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Integer, default=0)

    # Параметры поиска
    interests = Column(Text)
    recipient = Column(String(100))
    occasion = Column(String(100))

    is_favorite = Column(Boolean, default=False)

class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))

    # Запрос
    question = Column(Text, nullable=False)

    # Параметры
    interests = Column(Text)
    recipient = Column(String(100))
    occasion = Column(String(100))
    budget_min = Column(Integer)
    budget_max = Column(Integer)

    # Результат
    answer = Column(Text)

class DatabaseManager:

    @staticmethod
    async def get_session():
        """Получить сессию"""
        async with AsyncSessionLocal() as db:
            yield db

    @staticmethod
    async def get_or_create_user(session_id: str) -> User:
        """Получить или создать пользователя по id сессии"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.session_id == session_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(session_id=session_id)
                db.add(user)
                await db.commit()
                await db.refresh(user)

            return user

    @staticmethod
    async def get_user_by_id(user_id: str) -> User:
        """Получить пользователя по user_id"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def save_search(user_id: str, search_data: dict, answer: str) -> SearchHistory:
        """Сохранить историю поиска"""
        async with AsyncSessionLocal() as db:
            interests = search_data.get("interests")
            if isinstance(interests, list):
                interests = ", ".join(interests)
            history = SearchHistory(
                user_id=user_id,
                question=search_data.get("question"),
                recipient=search_data.get("recipient"),
                occasion=search_data.get("occasion"),
                interests=interests,
                budget_min=search_data.get("budget_min"),
                budget_max=search_data.get("budget_max"),
                answer=answer
            )
            db.add(history)
            await db.commit()
            await db.refresh(history)
            return history

    @staticmethod
    async def get_search_history(user_id: str):
        """Получить историю поиска пользователя"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SearchHistory)
                .where(SearchHistory.user_id == user_id)
                .order_by(desc(SearchHistory.id))
            )
            return result.scalars().all()

    @staticmethod
    async def get_search_history_by_id(history_id: int) -> SearchHistory:
        """Получить поиск по id"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SearchHistory)
                .where(SearchHistory.id == history_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def clear_search_history(user_id: str):
        """Очистить всю историю поиска пользователя"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(SearchHistory)
                .where(SearchHistory.user_id == user_id)
            )
            await db.commit()

    @staticmethod
    async def add_favorite(user_id: str, gift_data: dict) -> Gift:
        """Добавить подарок в избранное"""
        async with AsyncSessionLocal() as db:
            gift = Gift(
                user_id=user_id,
                name=gift_data.get("name"),
                description=gift_data.get("description"),
                price=gift_data.get("price"),
                interests=gift_data.get("interests"),
                recipient=gift_data.get("recipient"),
                occasion=gift_data.get("occasion"),
                is_favorite=True
            )
            db.add(gift)
            await db.commit()
            await db.refresh(gift)

            return gift

    @staticmethod
    async def remove_favorite(gift_id: int, user_id: str):
        """Удалить подарок из избранного"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(Gift)
                .where(Gift.id == gift_id,
                       Gift.user_id == user_id)
            )
            await db.commit()

    @staticmethod
    async def clear_all_favorites(user_id: str):
        """Очистить все избранное пользователя"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(Gift)
                .where(Gift.user_id == user_id,
                       Gift.is_favorite == True)
            )
            await db.commit()

async def init_db():
    """Инициализация БД"""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

async def close_db():
    """Закрытие соединения с БД"""
    await engine.dispose()