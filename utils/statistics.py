"""
Модуль для сбора и анализа статистики маршрутов.

Предоставляет функции для:
- Анализа времени прохождения маршрутов
- Расчета средних показателей
- Формирования статистических отчетов
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import RouteProgress, Route, User


async def get_route_statistics(
    session: AsyncSession,
    user_id: Optional[int] = None,
    days: Optional[int] = None
) -> Dict:
    """
    Получает статистику по маршрутам.
    
    Args:
        session: Сессия SQLAlchemy
        user_id: ID пользователя (опционально)
        days: Количество дней для выборки (опционально)
    
    Returns:
        Словарь со статистикой
    """
    # Базовый запрос
    query = select(RouteProgress).join(Route)
    
    # Добавляем фильтры
    if user_id:
        query = query.filter(RouteProgress.user_id == user_id)
    if days:
        date_from = datetime.now() - timedelta(days=days)
        query = query.filter(RouteProgress.visited_at >= date_from)
    
    # Получаем записи
    result = await session.execute(query)
    progresses = result.scalars().all()
    
    # Группируем по маршрутам
    routes_data = {}
    for progress in progresses:
        route_key = progress.route.city_name
        if route_key not in routes_data:
            routes_data[route_key] = {
                'total_routes': 0,
                'total_containers': 0,
                'total_time': timedelta(),
                'points_visited': 0,
                'completion_times': []
            }
        
        routes_data[route_key]['total_routes'] += 1
        routes_data[route_key]['total_containers'] += progress.containers_count
        routes_data[route_key]['points_visited'] += 1
        routes_data[route_key]['completion_times'].append(progress.visited_at)
    
    # Вычисляем средние значения и дополнительную статистику
    statistics = {
        'total_routes_completed': 0,
        'total_containers_collected': 0,
        'total_points_visited': 0,
        'routes_details': {},
        'top_performers': [],
        'busiest_days': []
    }
    
    for city, data in routes_data.items():
        # Сортируем времена посещения для анализа
        completion_times = sorted(data['completion_times'])
        if len(completion_times) >= 2:
            # Вычисляем среднее время между точками
            time_diffs = [
                (t2 - t1).total_seconds() / 60  # в минутах
                for t1, t2 in zip(completion_times[:-1], completion_times[1:])
            ]
            avg_time_between_points = sum(time_diffs) / len(time_diffs)
        else:
            avg_time_between_points = 0
        
        statistics['routes_details'][city] = {
            'total_routes': data['total_routes'],
            'total_containers': data['total_containers'],
            'points_visited': data['points_visited'],
            'avg_boxes_per_route': data['total_containers'] / data['total_routes'],
            'avg_time_between_points': avg_time_between_points
        }
        
        statistics['total_routes_completed'] += data['total_routes']
        statistics['total_containers_collected'] += data['total_containers']
        statistics['total_points_visited'] += data['points_visited']
    
    return statistics


async def get_user_performance(
    session: AsyncSession,
    days: Optional[int] = None,
    limit: int = 5
) -> List[Dict]:
    """
    Получает статистику производительности курьеров.
    
    Args:
        session: Сессия SQLAlchemy
        days: Количество дней для выборки (опционально)
        limit: Количество лучших курьеров для выборки
    
    Returns:
        Список словарей со статистикой по каждому курьеру
    """
    # Базовый запрос для подсчета статистики по пользователям
    query = (
        select(
            RouteProgress.user_id,
            func.count(RouteProgress.id).label('total_routes'),
            func.sum(RouteProgress.containers_count).label('total_containers')
        )
        .group_by(RouteProgress.user_id)
    )
    
    # Добавляем фильтр по дате если указан
    if days:
        date_from = datetime.now() - timedelta(days=days)
        query = query.filter(RouteProgress.visited_at >= date_from)
    
    # Получаем результаты
    result = await session.execute(query)
    stats = result.all()
    
    # Получаем информацию о пользователях
    user_stats = []
    for user_id, total_routes, total_containers in stats:
        user = await session.get(User, user_id)
        if user:
            user_stats.append({
                'user_id': user_id,
                'username': user.username or 'Неизвестный',
                'total_routes': total_routes,
                'total_containers': total_containers,
                'avg_boxes_per_route': total_containers / total_routes if total_routes else 0
            })
    
    # Сортируем по количеству собранных контейнеров
    user_stats.sort(key=lambda x: x['total_containers'], reverse=True)
    
    return user_stats[:limit]


async def get_busiest_days(
    session: AsyncSession,
    days: Optional[int] = None,
    limit: int = 5
) -> List[Dict]:
    """
    Получает статистику по самым загруженным дням.
    
    Args:
        session: Сессия SQLAlchemy
        days: Количество дней для выборки (опционально)
        limit: Количество дней для выборки
    
    Returns:
        Список словарей со статистикой по каждому дню
    """
    # Базовый запрос для группировки по дням
    query = (
        select(
            func.date(RouteProgress.visited_at).label('date'),
            func.count(RouteProgress.id).label('total_routes'),
            func.sum(RouteProgress.containers_count).label('total_containers')
        )
        .group_by(func.date(RouteProgress.visited_at))
    )
    
    # Добавляем фильтр по дате если указан
    if days:
        date_from = datetime.now() - timedelta(days=days)
        query = query.filter(RouteProgress.visited_at >= date_from)
    
    # Получаем результаты
    result = await session.execute(query)
    stats = result.all()
    
    # Форматируем результаты
    daily_stats = [
        {
            'date': date.strftime('%d.%m.%Y'),
            'total_routes': total_routes,
            'total_containers': total_containers,
            'avg_boxes_per_route': total_containers / total_routes if total_routes else 0
        }
        for date, total_routes, total_containers in stats
    ]
    
    # Сортируем по количеству маршрутов
    daily_stats.sort(key=lambda x: x['total_routes'], reverse=True)
    
    return daily_stats[:limit]


def format_statistics_message(statistics: Dict) -> str:
    """
    Форматирует статистику в читаемое сообщение для Telegram.
    
    Args:
        statistics: Словарь со статистикой
    
    Returns:
        Отформатированное сообщение
    """
    message_parts = [
        "📊 <b>Общая статистика маршрутов:</b>\n",
        f"🚚 Всего маршрутов: {statistics['total_routes_completed']}",
        f"📦 Всего собрано контейнеров: {statistics['total_containers_collected']}",
        f"📍 Всего посещено точек: {statistics['total_points_visited']}\n",
        "<b>Статистика по городам:</b>"
    ]
    
    for city, data in statistics['routes_details'].items():
        message_parts.extend([
            f"\n🏙 <b>{city}:</b>",
            f"• Маршрутов: {data['total_routes']}",
            f"• Собрано контейнеров: {data['total_containers']}",
            f"• Среднее время между точками: {data['avg_time_between_points']:.1f} мин"
        ])
    
    return "\n".join(message_parts)
