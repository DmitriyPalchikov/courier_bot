"""
Утилита для мониторинга маршрутов администратором.

Этот модуль содержит функции для получения информации о маршрутах,
их статусе, фотографиях и комментариях для административного интерфейса.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from database.database import get_session
from database.models import (
    RouteProgress, Route, User, RoutePhoto, LabSummary, LabSummaryPhoto,
    MoscowRoute, MoscowRoutePoint, Delivery
)

logger = logging.getLogger(__name__)


@dataclass
class RouteSessionInfo:
    """Информация о сессии маршрута."""
    session_id: str
    user_id: int
    username: str
    city_name: str
    start_time: datetime
    last_activity: datetime
    total_points: int
    completed_points: int
    total_containers: int
    status: str  # 'active', 'completed', 'paused'
    route_type: str  # 'collection', 'delivery'
    progress_percentage: float


@dataclass
class RoutePointDetails:
    """Детальная информация о точке маршрута."""
    point_name: str
    organization: str
    address: str
    containers_count: int
    notes: str
    visited_at: Optional[datetime]
    photos_count: int
    status: str


@dataclass
class MoscowRouteInfo:
    """Информация о маршруте в Москву."""
    route_id: int
    courier_id: Optional[int]
    courier_username: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    points_count: int
    total_containers: int


class RouteMonitor:
    """Класс для мониторинга маршрутов."""

    @staticmethod
    async def get_active_route_sessions() -> List[RouteSessionInfo]:
        """
        Получает список активных сессий маршрутов.
        
        Активным считается маршрут, который:
        1. Не имеет итогового комментария (не завершен)
        2. Имел активность в течение последних 3 дней
        3. Имеет хотя бы одну незавершенную точку
        
        Returns:
            List[RouteSessionInfo]: Список активных сессий
        """
        try:
            async for session in get_session():
                # Расширяем временное окно до 3 дней для более точного отслеживания
                cutoff_time = datetime.now() - timedelta(days=3)
                
                # Сначала находим все сессии без итогового комментария
                incomplete_sessions_query = select(
                    RouteProgress.route_session_id
                ).where(
                    and_(
                        RouteProgress.visited_at >= cutoff_time,
                        RouteProgress.route_session_id.isnot(None)
                    )
                ).group_by(RouteProgress.route_session_id).having(
                    # Исключаем сессии с итоговыми комментариями
                    func.sum(
                        func.case(
                            (
                                or_(
                                    RouteProgress.notes.like('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                                    RouteProgress.notes.like('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                                ), 1
                            ),
                            else_=0
                        )
                    ) == 0
                )
                
                incomplete_sessions = await session.execute(incomplete_sessions_query)
                active_session_ids = [row[0] for row in incomplete_sessions.fetchall()]
                
                if not active_session_ids:
                    return []
                
                # Теперь получаем детальную информацию только для активных сессий
                query = select(
                    RouteProgress.route_session_id,
                    RouteProgress.user_id,
                    User.username,
                    func.min(RouteProgress.visited_at).label('start_time'),
                    func.max(RouteProgress.visited_at).label('last_activity'),
                    func.count(RouteProgress.id).label('total_points'),
                    func.sum(RouteProgress.containers_count).label('total_containers')
                ).select_from(
                    RouteProgress.__table__.outerjoin(
                        User.__table__,
                        RouteProgress.user_id == User.telegram_id
                    )
                ).where(
                    RouteProgress.route_session_id.in_(active_session_ids)
                ).group_by(
                    RouteProgress.route_session_id,
                    RouteProgress.user_id,
                    User.username
                ).order_by(desc('last_activity'))
                
                result = await session.execute(query)
                sessions_data = result.fetchall()
                
                route_sessions = []
                
                for session_data in sessions_data:
                    session_id = session_data[0]
                    
                    # Получаем информацию о городе для данной сессии
                    city_info = await RouteMonitor._get_session_city_info(session_id, session)
                    if not city_info:
                        continue
                        
                    city_name = city_info['city_name']
                    
                    # Определяем статус сессии более точно
                    status = await RouteMonitor._determine_session_status(session_id, session)
                    
                    # Определяем тип маршрута
                    route_type = 'delivery' if city_name == 'Москва' else 'collection'
                    
                    # Подсчитываем завершенные точки (исключая итоговые комментарии)
                    completed_points_query = select(
                        func.count(RouteProgress.id)
                    ).where(
                        and_(
                            RouteProgress.route_session_id == session_id,
                            RouteProgress.status == 'completed',
                            RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                            RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                        )
                    )
                    completed_result = await session.execute(completed_points_query)
                    completed_points = completed_result.scalar() or 0
                    
                    # Рассчитываем процент завершения
                    total_points = session_data[5]  # Обновленный индекс после изменения запроса
                    progress_percentage = (completed_points / total_points * 100) if total_points > 0 else 0
                    
                    route_session = RouteSessionInfo(
                        session_id=session_id,
                        user_id=session_data[1],
                        username=session_data[2] or f"User_{session_data[1]}",
                        city_name=city_name,
                        start_time=session_data[3],
                        last_activity=session_data[4],
                        total_points=total_points,
                        completed_points=completed_points,
                        total_containers=session_data[6] or 0,
                        status=status,
                        route_type=route_type,
                        progress_percentage=progress_percentage
                    )
                    
                    route_sessions.append(route_session)
                
                return route_sessions
                
        except Exception as e:
            logger.error(f"Ошибка при получении активных маршрутов: {e}")
            return []

    @staticmethod
    async def get_completed_route_sessions(days: int = 7) -> List[RouteSessionInfo]:
        """
        Получает список завершенных сессий маршрутов за указанный период.
        
        Args:
            days: Количество дней для поиска
            
        Returns:
            List[RouteSessionInfo]: Список завершенных сессий
        """
        try:
            async for session in get_session():
                cutoff_time = datetime.now() - timedelta(days=days)
                
                # Ищем сессии с итоговыми комментариями или лабораторными данными
                final_comments_query = select(
                    RouteProgress.route_session_id,
                    RouteProgress.user_id,
                    User.username,
                    Route.city_name,
                    func.min(RouteProgress.visited_at).label('start_time'),
                    func.max(RouteProgress.visited_at).label('completion_time'),
                    func.count(RouteProgress.id).label('total_points'),
                    func.sum(RouteProgress.containers_count).label('total_containers')
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    ).outerjoin(
                        User.__table__,
                        RouteProgress.user_id == User.telegram_id
                    )
                ).where(
                    and_(
                        RouteProgress.visited_at >= cutoff_time,
                        RouteProgress.route_session_id.isnot(None),
                        or_(
                            RouteProgress.notes.like('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                            RouteProgress.notes.like('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                        )
                    )
                ).group_by(
                    RouteProgress.route_session_id,
                    RouteProgress.user_id,
                    User.username,
                    Route.city_name
                ).order_by(desc('completion_time'))
                
                result = await session.execute(final_comments_query)
                sessions_data = result.fetchall()
                
                route_sessions = []
                
                for session_data in sessions_data:
                    session_id = session_data[0]
                    
                    # Определяем тип маршрута
                    route_type = 'delivery' if session_data[3] == 'Москва' else 'collection'
                    
                    # Подсчитываем завершенные точки
                    completed_points_query = select(
                        func.count(RouteProgress.id)
                    ).where(
                        and_(
                            RouteProgress.route_session_id == session_id,
                            RouteProgress.status == 'completed',
                            RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                            RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                        )
                    )
                    completed_result = await session.execute(completed_points_query)
                    completed_points = completed_result.scalar() or 0
                    
                    total_points = session_data[6]
                    
                    route_session = RouteSessionInfo(
                        session_id=session_id,
                        user_id=session_data[1],
                        username=session_data[2] or f"User_{session_data[1]}",
                        city_name=session_data[3],
                        start_time=session_data[4],
                        last_activity=session_data[5],
                        total_points=total_points,
                        completed_points=completed_points,
                        total_containers=session_data[7] or 0,
                        status='completed',
                        route_type=route_type,
                        progress_percentage=100.0
                    )
                    
                    route_sessions.append(route_session)
                
                return route_sessions
                
        except Exception as e:
            logger.error(f"Ошибка при получении завершенных маршрутов: {e}")
            return []

    @staticmethod
    async def get_routes_by_city(city_name: str) -> List[RouteSessionInfo]:
        """
        Получает маршруты по указанному городу с правильной фильтрацией.
        
        Args:
            city_name: Название города
            
        Returns:
            List[RouteSessionInfo]: Список маршрутов по городу
        """
        try:
            async for session in get_session():
                # Сначала находим все сессии, где преобладает указанный город
                city_sessions_query = select(
                    RouteProgress.route_session_id,
                    func.count(
                        func.case(
                            (Route.city_name == city_name, 1),
                            else_=0
                        )
                    ).label('target_city_count'),
                    func.count(RouteProgress.id).label('total_count')
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    )
                ).where(
                    and_(
                        RouteProgress.route_session_id.isnot(None),
                        RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                        RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                    )
                ).group_by(
                    RouteProgress.route_session_id
                ).having(
                    # Сессия принадлежит городу, если более 70% точек из этого города
                    func.cast(
                        func.count(
                            func.case(
                                (Route.city_name == city_name, 1),
                                else_=0
                            )
                        ), Float
                    ) / func.cast(func.count(RouteProgress.id), Float) > 0.7
                )
                
                city_sessions_result = await session.execute(city_sessions_query)
                valid_sessions = [row[0] for row in city_sessions_result.fetchall()]
                
                if not valid_sessions:
                    return []
                
                # Теперь получаем детальную информацию только для валидных сессий
                query = select(
                    RouteProgress.route_session_id,
                    RouteProgress.user_id,
                    User.username,
                    func.min(RouteProgress.visited_at).label('start_time'),
                    func.max(RouteProgress.visited_at).label('last_activity'),
                    func.count(RouteProgress.id).label('total_points'),
                    func.sum(RouteProgress.containers_count).label('total_containers')
                ).select_from(
                    RouteProgress.__table__.outerjoin(
                        User.__table__,
                        RouteProgress.user_id == User.telegram_id
                    )
                ).where(
                    RouteProgress.route_session_id.in_(valid_sessions)
                ).group_by(
                    RouteProgress.route_session_id,
                    RouteProgress.user_id,
                    User.username
                ).order_by(desc('last_activity'))
                
                result = await session.execute(query)
                sessions_data = result.fetchall()
                
                route_sessions = []
                
                for session_data in sessions_data:
                    session_id = session_data[0]
                    
                    status = await RouteMonitor._determine_session_status(session_id, session)
                    route_type = 'delivery' if city_name == 'Москва' else 'collection'
                    
                    # Подсчитываем завершенные точки (исключая итоговые комментарии)
                    completed_points_query = select(
                        func.count(RouteProgress.id)
                    ).where(
                        and_(
                            RouteProgress.route_session_id == session_id,
                            RouteProgress.status == 'completed',
                            RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                            RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                        )
                    )
                    completed_result = await session.execute(completed_points_query)
                    completed_points = completed_result.scalar() or 0
                    
                    total_points = session_data[5]  # Обновленный индекс после изменения запроса
                    progress_percentage = (completed_points / total_points * 100) if total_points > 0 else 0
                    
                    route_session = RouteSessionInfo(
                        session_id=session_id,
                        user_id=session_data[1],
                        username=session_data[2] or f"User_{session_data[1]}",
                        city_name=city_name,  # Используем переданный город
                        start_time=session_data[3],
                        last_activity=session_data[4],
                        total_points=total_points,
                        completed_points=completed_points,
                        total_containers=session_data[6] or 0,
                        status=status,
                        route_type=route_type,
                        progress_percentage=progress_percentage
                    )
                    
                    route_sessions.append(route_session)
                
                return route_sessions
                
        except Exception as e:
            logger.error(f"Ошибка при получении маршрутов по городу {city_name}: {e}")
            return []

    @staticmethod
    async def get_routes_by_status(status: str) -> List[RouteSessionInfo]:
        """
        Получает маршруты по указанному статусу.
        
        Args:
            status: Статус маршрута ('active', 'paused', 'inactive', 'completed')
            
        Returns:
            List[RouteSessionInfo]: Список маршрутов с указанным статусом
        """
        try:
            if status == 'completed':
                return await RouteMonitor.get_completed_route_sessions(days=7)
            else:
                all_routes = await RouteMonitor.get_active_route_sessions()
                return [r for r in all_routes if r.status == status]
        except Exception as e:
            logger.error(f"Ошибка при получении маршрутов со статусом {status}: {e}")
            return []

    @staticmethod
    async def get_available_cities() -> List[str]:
        """
        Получает список доступных городов.
        
        Returns:
            List[str]: Список названий городов
        """
        try:
            async for session in get_session():
                query = select(Route.city_name).distinct().order_by(Route.city_name)
                result = await session.execute(query)
                cities = [row[0] for row in result.fetchall()]
                return cities
        except Exception as e:
            logger.error(f"Ошибка при получении списка городов: {e}")
            return []

    @staticmethod
    async def get_route_session_details(session_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает детальную информацию о сессии маршрута.
        
        Args:
            session_id: ID сессии маршрута
            
        Returns:
            Dict с детальной информацией о маршруте
        """
        try:
            async for session in get_session():
                # Получаем общую информацию о сессии
                session_query = select(
                    RouteProgress.user_id,
                    User.username,
                    Route.city_name,
                    func.min(RouteProgress.visited_at).label('start_time'),
                    func.max(RouteProgress.visited_at).label('last_activity')
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    ).outerjoin(
                        User.__table__,
                        RouteProgress.user_id == User.telegram_id
                    )
                ).where(
                    RouteProgress.route_session_id == session_id
                ).group_by(
                    RouteProgress.user_id,
                    User.username,
                    Route.city_name
                )
                
                session_result = await session.execute(session_query)
                session_info = session_result.first()
                
                if not session_info:
                    return None
                
                # Получаем детали по точкам
                points_query = select(
                    Route.point_name,
                    Route.organization,
                    Route.address,
                    RouteProgress.containers_count,
                    RouteProgress.notes,
                    RouteProgress.visited_at,
                    RouteProgress.status
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    )
                ).where(
                    and_(
                        RouteProgress.route_session_id == session_id,
                        RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                        RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                    )
                ).order_by(RouteProgress.visited_at)
                
                points_result = await session.execute(points_query)
                points_data = points_result.fetchall()
                
                # Получаем фотографии для каждой точки
                route_points = []
                for point_data in points_data:
                    # Подсчитываем фотографии для этой точки
                    photos_query = select(func.count(RoutePhoto.id)).where(
                        and_(
                            RoutePhoto.user_id == session_info[0],
                            RoutePhoto.route_session_id == session_id,
                            RoutePhoto.point_name == point_data[0]
                        )
                    )
                    photos_result = await session.execute(photos_query)
                    photos_count = photos_result.scalar() or 0
                    
                    point_details = RoutePointDetails(
                        point_name=point_data[0],
                        organization=point_data[1],
                        address=point_data[2],
                        containers_count=point_data[3] or 0,
                        notes=point_data[4] or "",
                        visited_at=point_data[5],
                        photos_count=photos_count,
                        status=point_data[6]
                    )
                    route_points.append(point_details)
                
                # Получаем итоговые комментарии
                final_comments_query = select(
                    RouteProgress.notes,
                    RouteProgress.visited_at
                ).where(
                    and_(
                        RouteProgress.route_session_id == session_id,
                        or_(
                            RouteProgress.notes.like('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                            RouteProgress.notes.like('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                        )
                    )
                ).order_by(RouteProgress.visited_at)
                
                final_result = await session.execute(final_comments_query)
                final_comments = final_result.fetchall()
                
                return {
                    'session_id': session_id,
                    'user_id': session_info[0],
                    'username': session_info[1] or f"User_{session_info[0]}",
                    'city_name': session_info[2],
                    'start_time': session_info[3],
                    'last_activity': session_info[4],
                    'route_type': 'delivery' if session_info[2] == 'Москва' else 'collection',
                    'points': route_points,
                    'final_comments': final_comments,
                    'total_points': len(route_points),
                    'completed_points': len([p for p in route_points if p.status == 'completed']),
                    'total_containers': sum(p.containers_count for p in route_points)
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении деталей маршрута {session_id}: {e}")
            return None

    @staticmethod
    async def get_moscow_routes() -> List[MoscowRouteInfo]:
        """
        Получает информацию о маршрутах в Москву.
        
        Returns:
            List[MoscowRouteInfo]: Список маршрутов в Москву
        """
        try:
            async for session in get_session():
                query = select(
                    MoscowRoute.id,
                    MoscowRoute.courier_id,
                    User.username,
                    MoscowRoute.status,
                    MoscowRoute.created_at,
                    MoscowRoute.completed_at,
                    func.count(MoscowRoutePoint.id).label('points_count'),
                    func.sum(MoscowRoutePoint.containers_to_deliver).label('total_containers')
                ).select_from(
                    MoscowRoute.__table__.outerjoin(
                        User.__table__,
                        MoscowRoute.courier_id == User.telegram_id
                    ).outerjoin(
                        MoscowRoutePoint.__table__,
                        MoscowRoute.id == MoscowRoutePoint.moscow_route_id
                    )
                ).group_by(
                    MoscowRoute.id,
                    MoscowRoute.courier_id,
                    User.username,
                    MoscowRoute.status,
                    MoscowRoute.created_at,
                    MoscowRoute.completed_at
                ).order_by(desc(MoscowRoute.created_at))
                
                result = await session.execute(query)
                routes_data = result.fetchall()
                
                moscow_routes = []
                for route_data in routes_data:
                    moscow_route = MoscowRouteInfo(
                        route_id=route_data[0],
                        courier_id=route_data[1],
                        courier_username=route_data[2] or (f"User_{route_data[1]}" if route_data[1] else "Не назначен"),
                        status=route_data[3],
                        created_at=route_data[4],
                        completed_at=route_data[5],
                        points_count=route_data[6] or 0,
                        total_containers=route_data[7] or 0
                    )
                    moscow_routes.append(moscow_route)
                
                return moscow_routes
                
        except Exception as e:
            logger.error(f"Ошибка при получении маршрутов в Москву: {e}")
            return []

    @staticmethod
    async def _get_session_city_info(session_id: str, session) -> Optional[Dict[str, str]]:
        """
        Получает информацию о городе для сессии маршрута.
        
        Args:
            session_id: ID сессии
            session: Сессия базы данных
            
        Returns:
            Dict с информацией о городе или None
        """
        try:
            # Получаем наиболее часто встречающийся город в сессии
            city_query = select(
                Route.city_name,
                func.count(RouteProgress.id).label('count')
            ).select_from(
                RouteProgress.__table__.join(
                    Route.__table__,
                    RouteProgress.route_id == Route.id
                )
            ).where(
                and_(
                    RouteProgress.route_session_id == session_id,
                    RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                    RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                )
            ).group_by(Route.city_name).order_by(desc('count')).limit(1)
            
            result = await session.execute(city_query)
            city_data = result.first()
            
            if city_data:
                return {
                    'city_name': city_data[0],
                    'points_count': city_data[1]
                }
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о городе для сессии {session_id}: {e}")
            return None

    @staticmethod
    async def _determine_session_status(session_id: str, session) -> str:
        """
        Определяет статус сессии маршрута более точно.
        
        Args:
            session_id: ID сессии
            session: Сессия базы данных
            
        Returns:
            str: Статус сессии ('active', 'paused', 'completed', 'unknown')
        """
        try:
            # Проверяем наличие итогового комментария
            final_comment_query = select(RouteProgress.id).where(
                and_(
                    RouteProgress.route_session_id == session_id,
                    or_(
                        RouteProgress.notes.like('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                        RouteProgress.notes.like('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                    )
                )
            )
            final_result = await session.execute(final_comment_query)
            has_final_comment = final_result.first() is not None
            
            if has_final_comment:
                return 'completed'
            
            # Получаем информацию о последней активности и прогрессе
            progress_query = select(
                func.max(RouteProgress.visited_at).label('last_activity'),
                func.count(RouteProgress.id).label('total_points'),
                func.sum(
                    func.case(
                        (RouteProgress.status == 'completed', 1),
                        else_=0
                    )
                ).label('completed_points')
            ).where(
                and_(
                    RouteProgress.route_session_id == session_id,
                    RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                    RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
                )
            )
            
            progress_result = await session.execute(progress_query)
            progress_data = progress_result.first()
            
            if not progress_data or not progress_data[0]:
                return 'unknown'
            
            last_activity = progress_data[0]
            total_points = progress_data[1] or 0
            completed_points = progress_data[2] or 0
            
            # Определяем статус на основе времени последней активности
            hours_since_activity = (datetime.now() - last_activity).total_seconds() / 3600
            
            if hours_since_activity <= 2:  # Активность в последние 2 часа
                return 'active'
            elif hours_since_activity <= 24:  # Активность в последние 24 часа
                return 'paused'
            else:  # Давняя активность, но маршрут не завершен
                # Если большинство точек завершено, но нет итогового комментария - вероятно заброшен
                completion_rate = (completed_points / total_points) if total_points > 0 else 0
                if completion_rate > 0.8:  # Если завершено более 80% точек
                    return 'paused'
                else:
                    return 'inactive'  # Новый статус для старых незавершенных маршрутов
            
        except Exception as e:
            logger.error(f"Ошибка при определении статуса сессии {session_id}: {e}")
            return 'unknown'
