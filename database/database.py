"""
Модуль для работы с базой данных.

Содержит функции для инициализации базы данных,
создания асинхронных сессий и управления подключениями.

Используется SQLAlchemy с асинхронным драйвером aiosqlite для SQLite.
"""

import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker
)
from sqlalchemy.pool import StaticPool

from config import DATABASE_URL
from .models import Base

logger = logging.getLogger(__name__)

# Создаём асинхронный движок для работы с базой данных
# StaticPool используется для SQLite чтобы избежать проблем с многопоточностью
engine = create_async_engine(
    DATABASE_URL,
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False,  # Для SQLite: разрешаем использование из разных потоков
    },
    echo=False  # Установите True для отладки SQL-запросов
)

# Создаём фабрику сессий для работы с базой данных
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # Объекты остаются доступными после коммита
)


async def init_db() -> None:
    """
    Инициализирует базу данных.
    
    Создаёт все необходимые таблицы согласно определённым моделям.
    Эта функция должна вызываться при запуске приложения.
    
    Raises:
        Exception: Если произошла ошибка при создании таблиц
    """
    try:
        logger.info("Начинаем создание таблиц базы данных...")
        
        # Создаём все таблицы асинхронно
        async with engine.begin() as conn:
            # Создаём таблицы согласно метаданным наших моделей
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Таблицы базы данных успешно созданы")
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Генератор асинхронных сессий для работы с базой данных.
    
    Используется как dependency injection в хендлерах бота.
    Автоматически закрывает сессию после использования.
    
    Yields:
        AsyncSession: Асинхронная сессия для работы с БД
        
    Example:
        async def some_handler():
            async for session in get_session():
                # Работаем с базой данных
                user = await session.get(User, user_id)
                # Сессия автоматически закроется после выхода из блока
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            # В случае ошибки откатываем изменения
            await session.rollback()
            logger.error(f"Ошибка при работе с базой данных: {e}")
            raise
        finally:
            # Закрываем сессию
            await session.close()


async def close_db() -> None:
    """
    Закрывает соединения с базой данных.
    
    Должна вызываться при остановке приложения для корректного
    освобождения ресурсов.
    """
    try:
        await engine.dispose()
        logger.info("Соединения с базой данных закрыты")
    except Exception as e:
        logger.error(f"Ошибка при закрытии соединений с БД: {e}")


# Функция для получения одной сессии (используется реже)
async def get_single_session() -> AsyncSession:
    """
    Получает одну асинхронную сессию.
    
    ВНИМАНИЕ: При использовании этой функции необходимо самостоятельно
    закрывать сессию после использования!
    
    Returns:
        AsyncSession: Асинхронная сессия
        
    Example:
        session = await get_single_session()
        try:
            # Работаем с базой данных
            pass
        finally:
            await session.close()
    """
    return async_session_maker()
