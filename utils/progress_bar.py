"""
Утилиты для визуализации прогресса маршрута в Telegram.

Этот модуль предоставляет функции для создания визуального
прогресс-бара и форматирования сообщений о прогрессе маршрута.
"""

from typing import Dict, List, Tuple
from aiogram.utils.markdown import bold, italic


def create_progress_bar(current: int, total: int, width: int = 10) -> str:
    """
    Создает ASCII прогресс-бар для отображения в Telegram.
    
    Args:
        current: Текущая позиция
        total: Общее количество шагов
        width: Ширина прогресс-бара в символах
    
    Returns:
        Строка с прогресс-баром
    """
    filled = int(width * current / total)
    empty = width - filled
    
    # Используем эмодзи для более красивого отображения
    bar = "🟦" * filled + "⬜️" * empty
    percentage = int(100 * current / total)
    
    return f"{bar} {percentage}%"


def format_route_progress(
    city: str,
    current_point: Dict,
    total_points: int,
    current_index: int,
    collected_containers: Dict[str, int]
) -> str:
    """
    Форматирует сообщение о прогрессе маршрута.
    
    Args:
        city: Название города
        current_point: Информация о текущей точке
        total_points: Общее количество точек
        current_index: Текущий индекс (0-based)
        collected_containers: Словарь с количеством собранных контейнеров по организациям
    
    Returns:
        Отформатированное сообщение с прогресс-баром
    """
    # Создаем прогресс-бар
    progress = create_progress_bar(current_index + 1, total_points)
    
    # Формируем статистику по собранным контейнерам
    containers_info = []
    total_containers = 0
    for org, count in collected_containers.items():
        containers_info.append(f"• {org}: {count} 📦")
        total_containers += count
    
    # Собираем сообщение
    message_parts = [
        f"🏙️ {bold(f'Маршрут: {city}')}",
        f"📍 {bold(f'Точка {current_index + 1} из {total_points}')}",
        f"\n{progress}\n",
        f"🏢 {bold('Организация:')} {current_point['organization']}",
        f"📍 {bold('Адрес:')} {current_point['address']}",
    ]
    
    # Добавляем информацию о собранных контейнерах, если они есть
    if containers_info:
        message_parts.extend([
            f"\n📊 {bold('Собрано контейнеров:')}",
            *containers_info,
            f"📦 {bold(f'Всего: {total_containers}')}"
        ])
    
    return "\n".join(message_parts)


def format_route_summary(
    city: str,
    total_points: int,
    collected_containers: Dict[str, int],
    total_time: str
) -> str:
    """
    Форматирует итоговое сообщение о завершенном маршруте.
    
    Args:
        city: Название города
        total_points: Общее количество точек
        collected_containers: Словарь с количеством собранных контейнеров по организациям
        total_time: Общее время прохождения маршрута
    
    Returns:
        Отформатированное сообщение с итогами маршрута
    """
    # Создаем прогресс-бар (полностью заполненный)
    progress = create_progress_bar(total_points, total_points)
    
    # Формируем статистику по собранным контейнерам
    containers_info = []
    total_containers = 0
    for org, count in collected_containers.items():
        containers_info.append(f"• {org}: {count} 📦")
        total_containers += count
    
    # Собираем сообщение
    message_parts = [
        f"✅ {bold(f'Маршрут {city} завершен!')}",
        f"\n{progress}\n",
        f"📊 {bold('Итоги маршрута:')}",
        f"📍 Посещено точек: {total_points}",
        f"⏱ Общее время: {total_time}",
        f"\n📦 {bold('Собрано контейнеров:')}",
        *containers_info,
        f"\n{bold(f'Всего собрано: {total_containers} 📦')}"
    ]
    
    return "\n".join(message_parts)
