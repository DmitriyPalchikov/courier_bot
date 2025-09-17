#!/usr/bin/env python3
"""
Миграция для добавления таблиц lab_summaries и lab_summary_photos.

Эти таблицы нужны для хранения итоговых данных по лабораториям
после завершения всех точек маршрута.
"""

import asyncio
import sys
import os

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.database import engine


async def add_lab_summaries_tables():
    """Создает таблицы для итоговых данных по лабораториям."""
    
    async with engine.begin() as conn:
        # Создаем таблицу lab_summaries
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS lab_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                route_session_id VARCHAR(50) NOT NULL,
                organization VARCHAR(50) NOT NULL,
                summary_comment TEXT,
                is_completed BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
            );
        """))
        
        print("✅ Таблица lab_summaries создана")
        
        # Создаем таблицу lab_summary_photos
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS lab_summary_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lab_summary_id INTEGER NOT NULL,
                photo_file_id VARCHAR(255) NOT NULL,
                photo_order INTEGER DEFAULT 1,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lab_summary_id) REFERENCES lab_summaries (id) ON DELETE CASCADE
            );
        """))
        
        print("✅ Таблица lab_summary_photos создана")
        
        # Создаем индексы для оптимизации запросов
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_lab_summaries_session 
            ON lab_summaries (route_session_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_lab_summaries_user 
            ON lab_summaries (user_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_lab_summary_photos_lab 
            ON lab_summary_photos (lab_summary_id);
        """))
        
        print("✅ Индексы созданы")
        
        print("🎉 Миграция завершена успешно!")


if __name__ == "__main__":
    asyncio.run(add_lab_summaries_tables())
