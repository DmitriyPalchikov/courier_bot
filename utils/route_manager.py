"""
Утилиты для управления маршрутами курьерского бота.

Содержит класс RouteManager для работы с маршрутами:
- Инициализация маршрутов в базе данных
- Расчёт прогресса прохождения
- Формирование отчётов
- Оптимизация маршрутов
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from database.database import get_session
from database.models import User, Route, RouteProgress, Delivery
from config import AVAILABLE_ROUTES, MOSCOW_DELIVERY_ADDRESSES

logger = logging.getLogger(__name__)


@dataclass
class RoutePoint:
    """Класс для представления точки маршрута."""
    name: str
    address: str
    organization: str
    coordinates: Optional[Tuple[float, float]] = None
    order_index: int = 0
    is_completed: bool = False
    boxes_collected: int = 0


@dataclass
class RouteStats:
    """Класс для статистики маршрута."""
    total_points: int
    completed_points: int
    total_containers: int
    organizations: List[str]
    completion_percentage: float
    estimated_completion_time: Optional[datetime] = None


class RouteManager:
    """
    Менеджер для работы с маршрутами.
    
    Предоставляет методы для:
    - Инициализации маршрутов
    - Отслеживания прогресса
    - Формирования отчётов
    - Оптимизации доставок
    """
    
    @staticmethod
    async def initialize_routes_in_db() -> None:
        """
        Инициализирует маршруты из конфигурации в базе данных.
        
        Создаёт записи маршрутов если они ещё не существуют.
        Обновляет существующие записи при необходимости.
        """
        logger.info("Начинаем инициализацию маршрутов в БД...")
        
        async for session in get_session():
            routes_added = 0
            routes_updated = 0
            
            for city_name, points in AVAILABLE_ROUTES.items():
                for index, point_config in enumerate(points):
                    # Проверяем, существует ли уже такая точка маршрута
                    stmt = select(Route).where(
                        and_(
                            Route.city_name == city_name,
                            Route.point_name == point_config['name'],
                            Route.organization == point_config['organization']
                        )
                    )
                    existing_route = await session.scalar(stmt)
                    
                    if not existing_route:
                        # Создаём новую запись маршрута
                        coordinates = point_config.get('coordinates', (None, None))
                        new_route = Route(
                            city_name=city_name,
                            point_name=point_config['name'],
                            address=point_config['address'],
                            organization=point_config['organization'],
                            latitude=coordinates if coordinates else None,
                            longitude=coordinates if coordinates else None,
                            order_index=index,
                            is_active=True
                        )
                        session.add(new_route)
                        routes_added += 1
                        
                        logger.debug(f"Добавлен маршрут: {city_name} - {point_config['name']}")
                    
                    else:
                        # Обновляем существующую запись при необходимости
                        updated = False
                        
                        if existing_route.address != point_config['address']:
                            existing_route.address = point_config['address']
                            updated = True
                        
                        if existing_route.order_index != index:
                            existing_route.order_index = index
                            updated = True
                        
                        coordinates = point_config.get('coordinates', (None, None))
                        if coordinates and (existing_route.latitude != coordinates or 
                                          existing_route.longitude != coordinates):
                            existing_route.latitude = coordinates
                            existing_route.longitude = coordinates
                            updated = True
                        
                        if updated:
                            routes_updated += 1
                            logger.debug(f"Обновлён маршрут: {city_name} - {point_config['name']}")
            
            await session.commit()
            
            logger.info(f"Инициализация завершена. Добавлено: {routes_added}, обновлено: {routes_updated}")
    
    
    @staticmethod
    async def get_user_active_route(user_id: int) -> Optional[Dict]:
        """
        Получает активный маршрут пользователя.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Optional[Dict]: Информация об активном маршруте или None
        """
        async for session in get_session():
            # Ищем незавершённые записи прогресса пользователя
            stmt = select(RouteProgress).options(
                selectinload(RouteProgress.route)
            ).where(
                and_(
                    RouteProgress.user_id == user_id,
                    RouteProgress.status.in_(['pending', 'in_progress'])
                )
            ).order_by(RouteProgress.created_at.desc()).limit(1)
            
            active_progress = await session.scalar(stmt)
            
            if not active_progress:
                return None
            
            # Получаем все точки этого города
            city_routes_stmt = select(Route).where(
                Route.city_name == active_progress.route.city_name
            ).order_by(Route.order_index)
            
            city_routes = await session.scalars(city_routes_stmt)
            city_routes_list = city_routes.all()
            
            # Получаем прогресс по всем точкам этого города для пользователя
            user_progress_stmt = select(RouteProgress).where(
                and_(
                    RouteProgress.user_id == user_id,
                    RouteProgress.route_id.in_([r.id for r in city_routes_list])
                )
            ).order_by(RouteProgress.created_at)
            
            user_progresses = await session.scalars(user_progress_stmt)
            user_progresses_list = user_progresses.all()
            
            return {
                'city_name': active_progress.route.city_name,
                'current_point_index': len(user_progresses_list),
                'total_points': len(city_routes_list),
                'completed_points': [p.route_id for p in user_progresses_list],
                'routes': city_routes_list,
                'progresses': user_progresses_list
            }
    
    
    @staticmethod
    async def get_route_statistics(user_id: Optional[int] = None, 
                                 city_name: Optional[str] = None,
                                 date_from: Optional[datetime] = None,
                                 date_to: Optional[datetime] = None) -> RouteStats:
        """
        Получает статистику по маршрутам.
        
        Args:
            user_id: ID пользователя (опционально)
            city_name: Название города (опционально)
            date_from: Дата начала периода (опционально)
            date_to: Дата окончания периода (опционально)
            
        Returns:
            RouteStats: Статистика маршрутов
        """
        async for session in get_session():
            # Базовый запрос
            stmt = select(RouteProgress).options(
                selectinload(RouteProgress.route)
            )
            
            # Добавляем фильтры
            conditions = []
            if user_id:
                conditions.append(RouteProgress.user_id == user_id)
            if city_name:
                conditions.append(Route.city_name == city_name)
            if date_from:
                conditions.append(RouteProgress.visited_at >= date_from)
            if date_to:
                conditions.append(RouteProgress.visited_at <= date_to)
            
            if conditions:
                stmt = stmt.join(Route).where(and_(*conditions))
            
            progresses = await session.scalars(stmt)
            progresses_list = progresses.all()
            
            if not progresses_list:
                return RouteStats(
                    total_points=0,
                    completed_points=0,
                    total_containers=0,
                    organizations=[],
                    completion_percentage=0.0
                )
            
            # Подсчитываем статистику
            total_points = len(progresses_list)
            completed_points = len([p for p in progresses_list if p.status == 'completed'])
            total_containers = sum(p.containers_count for p in progresses_list)
            organizations = list(set(p.route.organization for p in progresses_list))
            completion_percentage = (completed_points / total_points * 100) if total_points > 0 else 0
            
            return RouteStats(
                total_points=total_points,
                completed_points=completed_points,
                total_containers=total_containers,
                organizations=organizations,
                completion_percentage=completion_percentage
            )
    
    
    @staticmethod
    async def generate_delivery_summary() -> Dict[str, Any]:
        """
        Генерирует сводку готовых к доставке товаров.
        
        Returns:
            Dict[str, Any]: Сводка по доставкам
        """
        async for session in get_session():
            # Получаем все pending доставки
            stmt = select(Delivery).where(
                Delivery.status == 'pending'
            ).order_by(Delivery.created_at)
            
            pending_deliveries = await session.scalars(stmt)
            deliveries_list = pending_deliveries.all()
            
            if not deliveries_list:
                return {
                    'total_deliveries': 0,
                    'total_containers': 0,
                    'organizations': {},
                    'estimated_trips': 0,
                    'priority_deliveries': []
                }
            
            # Группируем по организациям
            organizations_summary = {}
            total_containers = 0
            
            for delivery in deliveries_list:
                org = delivery.organization
                if org not in organizations_summary:
                    organizations_summary[org] = {
                        'total_containers': 0,
                        'deliveries_count': 0,
                        'address': MOSCOW_DELIVERY_ADDRESSES.get(org, {}).get('address', 'Не указан'),
                        'contact': MOSCOW_DELIVERY_ADDRESSES.get(org, {}).get('contact', 'Не указан'),
                        'working_hours': MOSCOW_DELIVERY_ADDRESSES.get(org, {}).get('working_hours', 'Не указано')
                    }
                
                organizations_summary[org]['total_containers'] += delivery.total_containers
                organizations_summary[org]['deliveries_count'] += 1
                total_containers += delivery.total_containers
            
            # Оцениваем количество необходимых поездок (условно 50 коробок за поездку)
            estimated_trips = max(1, (total_containers + 49) // 50)
            
            # Определяем приоритетные доставки (большие объёмы)
            priority_deliveries = [
                org for org, data in organizations_summary.items() 
                if data['total_containers'] >= 20
            ]
            
            return {
                'total_deliveries': len(deliveries_list),
                'total_containers': total_containers,
                'organizations': organizations_summary,
                'estimated_trips': estimated_trips,
                'priority_deliveries': priority_deliveries,
                'generation_time': datetime.utcnow()
            }
    
    
    @staticmethod
    async def optimize_route_order(city_name: str) -> List[Dict]:
        """
        Оптимизирует порядок объезда точек в маршруте.
        
        Простая оптимизация на основе географической близости
        и приоритета организаций.
        
        Args:
            city_name: Название города
            
        Returns:
            List[Dict]: Оптимизированный порядок точек
        """
        if city_name not in AVAILABLE_ROUTES:
            return []
        
        points = AVAILABLE_ROUTES[city_name].copy()
        
        # Простая эвристическая оптимизация:
        # 1. Сначала КДЛ (обычно имеют больше товаров)
        # 2. Потом остальные по географической близости
        
        kdl_points = [p for p in points if p['organization'] == 'КДЛ']
        other_points = [p for p in points if p['organization'] != 'КДЛ']
        
        # Сортируем КДЛ по названию для стабильности
        kdl_points.sort(key=lambda x: x['name'])
        
        # Сортируем остальные по организации, потом по названию
        other_points.sort(key=lambda x: (x['organization'], x['name']))
        
        # Объединяем оптимизированный маршрут
        optimized_route = kdl_points + other_points
        
        # Добавляем индексы порядка
        for index, point in enumerate(optimized_route):
            point['optimized_order'] = index
        
        logger.info(f"Маршрут для {city_name} оптимизирован: {len(optimized_route)} точек")
        
        return optimized_route
    
    
    @staticmethod
    async def cleanup_old_data(days_to_keep: int = 30) -> Dict[str, int]:
        """
        Очищает старые данные из базы.
        
        Args:
            days_to_keep: Количество дней для хранения данных
            
        Returns:
            Dict[str, int]: Статистика удалённых записей
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        async for session in get_session():
            # Удаляем старые прогрессы маршрутов
            old_progresses = await session.execute(
                select(RouteProgress).where(
                    RouteProgress.visited_at < cutoff_date
                )
            )
            old_progresses_count = len(old_progresses.scalars().all())
            
            if old_progresses_count > 0:
                await session.execute(
                    RouteProgress.__table__.delete().where(
                        RouteProgress.visited_at < cutoff_date
                    )
                )
            
            # Удаляем старые завершённые доставки
            old_deliveries = await session.execute(
                select(Delivery).where(
                    and_(
                        Delivery.delivered_at < cutoff_date,
                        Delivery.status == 'completed'
                    )
                )
            )
            old_deliveries_count = len(old_deliveries.scalars().all())
            
            if old_deliveries_count > 0:
                await session.execute(
                    Delivery.__table__.delete().where(
                        and_(
                            Delivery.delivered_at < cutoff_date,
                            Delivery.status == 'completed'
                        )
                    )
                )
            
            await session.commit()
            
            logger.info(f"Удалено старых записей: прогрессы={old_progresses_count}, доставки={old_deliveries_count}")
            
            return {
                'route_progresses_deleted': old_progresses_count,
                'deliveries_deleted': old_deliveries_count,
                'cutoff_date': cutoff_date.isoformat()
            }
