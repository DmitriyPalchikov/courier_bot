"""
Главный файл для запуска Telegram-бота курьерской службы.

Этот файл содержит основную точку входа в приложение и инициализацию
всех необходимых компонентов бота.

Автор: Senior Python Developer
Дата: Сентябрь 2025
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импортируем наши модули
from config import BOT_TOKEN, DATABASE_URL
from database.database import init_db
from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router


# Настройка логирования для отслеживания работы бота
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """
    Главная асинхронная функция для запуска бота.
    
    Эта функция:
    1. Инициализирует объект бота с токеном
    2. Создаёт диспетчер для обработки событий
    3. Инициализирует базу данных
    4. Подключает роутеры для обработки сообщений
    5. Запускает поллинг (получение обновлений от Telegram)
    """
    try:
        # Создаём объект бота с настройками по умолчанию
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Создаём диспетчер - центральный компонент для обработки событий
        dp = Dispatcher()
        
        # Инициализируем базу данных (создаём таблицы если их нет)
        logger.info("Инициализация базы данных...")
        try:
            await init_db()
            logger.info("База данных успешно инициализирована")
        except Exception as db_error:
            logger.error(f"Ошибка инициализации БД: {db_error}")
            logger.info("Попытка пересоздать базу данных...")
            import os
            if os.path.exists("courier_bot.db"):
                os.remove("courier_bot.db")
            await init_db()
            logger.info("База данных пересоздана успешно")
        
        # Подключаем роутеры в правильном порядке (важно!)
        # Роутер администратора должен быть первым для приоритета
        dp.include_router(admin_router)
        dp.include_router(user_router)
        
        logger.info("Роутеры подключены успешно")
        
        # Удаляем webhook если он был установлен ранее
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем поллинг - бот начинает получать сообщения
        logger.info("Бот запущен и готов к работе!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise


if __name__ == '__main__':
    """
    Точка входа в программу.
    Запускаем главную асинхронную функцию.
    """
    try:
        # Запускаем асинхронное приложение
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")