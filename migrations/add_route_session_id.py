#!/usr/bin/env python3
"""
Миграция для добавления поля route_session_id в таблицу route_progress.
"""

import asyncio
from sqlalchemy import text
from database.database import get_engine


async def add_route_session_id_column():
    """Добавляет поле route_session_id в таблицу route_progress."""
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Добавляем новое поле
        await conn.execute(text("""
            ALTER TABLE route_progress 
            ADD COLUMN route_session_id VARCHAR(50) NOT NULL DEFAULT 'legacy_session';
        """))
        
        print("✅ Поле route_session_id добавлено в таблицу route_progress")
        
        # Обновляем существующие записи, создавая уникальные session_id
        await conn.execute(text("""
            UPDATE route_progress 
            SET route_session_id = CONCAT(
                user_id, '_', 
                (SELECT city_name FROM routes WHERE routes.id = route_progress.route_id), '_',
                DATE_FORMAT(visited_at, '%Y%m%d_%H%i%s'), '_',
                LPAD(id, 8, '0')
            )
            WHERE route_session_id = 'legacy_session';
        """))
        
        print("✅ Существующие записи обновлены с уникальными session_id")
        
        # Убираем значение по умолчанию
        await conn.execute(text("""
            ALTER TABLE route_progress 
            ALTER COLUMN route_session_id DROP DEFAULT;
        """))
        
        print("✅ Значение по умолчанию удалено")


if __name__ == "__main__":
    asyncio.run(add_route_session_id_column())
