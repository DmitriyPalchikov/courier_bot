"""
Менеджер callback данных для работы с ограничениями Telegram API.

Telegram ограничивает callback_data до 64 байт. Этот модуль предоставляет
функции для создания коротких callback_data и их последующего восстановления.
"""

import hashlib
import json
from typing import Dict, Any, Optional

# Глобальное хранилище для callback данных
_callback_storage: Dict[str, Any] = {}


def generate_short_callback(data: Any) -> str:
    """
    Генерирует короткий callback_data для данных.
    
    Args:
        data: Данные для сохранения (может быть строкой, числом, словарем)
        
    Returns:
        str: Короткий callback_data (до 64 байт)
    """
    # Преобразуем данные в строку
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    else:
        data_str = str(data)
    
    # Создаем хеш от данных
    hash_object = hashlib.md5(data_str.encode('utf-8'))
    short_id = hash_object.hexdigest()[:12]  # Используем первые 12 символов MD5
    
    # Сохраняем в хранилище
    _callback_storage[short_id] = data
    
    return short_id


def get_callback_data(short_id: str) -> Optional[Any]:
    """
    Восстанавливает данные по короткому ID.
    
    Args:
        short_id: Короткий ID callback данных
        
    Returns:
        Any: Восстановленные данные или None если не найдены
    """
    return _callback_storage.get(short_id)


def create_route_callback(route_id: str) -> str:
    """
    Создает callback для просмотра маршрута.
    
    Args:
        route_id: ID маршрута (может быть длинным)
        
    Returns:
        str: Короткий callback_data
    """
    callback_data = {
        'action': 'view_route',
        'route_id': route_id
    }
    short_id = generate_short_callback(callback_data)
    return f"r:{short_id}"


def create_route_point_callback(route_id: str, point_index: int) -> str:
    """
    Создает callback для просмотра точки маршрута.
    
    Args:
        route_id: ID маршрута
        point_index: Индекс точки
        
    Returns:
        str: Короткий callback_data
    """
    callback_data = {
        'action': 'route_point',
        'route_id': route_id,
        'point_index': point_index
    }
    short_id = generate_short_callback(callback_data)
    return f"rp:{short_id}"


def create_photo_callback(route_id: str, point_index: int, photo_index: int) -> str:
    """
    Создает callback для просмотра фотографии.
    
    Args:
        route_id: ID маршрута
        point_index: Индекс точки
        photo_index: Индекс фотографии
        
    Returns:
        str: Короткий callback_data
    """
    callback_data = {
        'action': 'view_photo',
        'route_id': route_id,
        'point_index': point_index,
        'photo_index': photo_index
    }
    short_id = generate_short_callback(callback_data)
    return f"p:{short_id}"


def parse_callback(callback_data: str) -> Optional[Dict[str, Any]]:
    """
    Парсит callback_data и возвращает исходные данные.
    
    Args:
        callback_data: Callback данные от Telegram
        
    Returns:
        Dict[str, Any]: Распарсенные данные или None
    """
    if ':' not in callback_data:
        return None
    
    prefix, short_id = callback_data.split(':', 1)
    return get_callback_data(short_id)


def clear_old_callbacks(keep_recent: int = 1000) -> None:
    """
    Очищает старые callback данные, оставляя только последние.
    
    Args:
        keep_recent: Количество последних записей для сохранения
    """
    global _callback_storage
    
    if len(_callback_storage) > keep_recent:
        # Удаляем старые записи (простая очистка)
        items = list(_callback_storage.items())
        _callback_storage = dict(items[-keep_recent:])
