"""
Утилиты для работы с сессиями маршрутов.
"""

import uuid
from datetime import datetime


def generate_route_session_id(user_id: int, city: str) -> str:
    """
    Генерирует уникальный ID для сессии маршрута.
    
    Args:
        user_id: ID пользователя
        city: Название города
        
    Returns:
        str: Уникальный ID сессии маршрута
    """
    # Используем UUID4 для уникальности + timestamp + user_id + city
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_part = str(uuid.uuid4())[:8]  # Первые 8 символов UUID
    
    return f"{user_id}_{city}_{timestamp}_{uuid_part}"


def parse_route_session_id(session_id: str) -> dict:
    """
    Парсит ID сессии маршрута для получения информации.
    
    Args:
        session_id: ID сессии маршрута
        
    Returns:
        dict: Словарь с информацией о сессии
    """
    parts = session_id.split("_")
    if len(parts) < 4:
        raise ValueError("Неверный формат ID сессии маршрута")
    
    return {
        "user_id": int(parts[0]),
        "city": parts[1],
        "date": parts[2],
        "time": parts[3],
        "uuid": parts[4] if len(parts) > 4 else ""
    }
