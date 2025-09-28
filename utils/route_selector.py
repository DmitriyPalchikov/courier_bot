"""
Утилиты для выбора маршрутов пользователями.

Содержит функции для:
- Получения всех доступных маршрутов (сбор + доставка)
- Формирования клавиатур выбора маршрутов
- Определения типа маршрута
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select

from database.database import get_session
from database.models import MoscowRoute, MoscowRoutePoint
from config import AVAILABLE_ROUTES

logger = logging.getLogger(__name__)


class RouteSelector:
    """
    Класс для работы с выбором маршрутов пользователями.
    
    Объединяет статические маршруты сбора (из config.py) 
    и динамические маршруты доставки в Москву.
    """
    
    @staticmethod
    async def get_all_available_routes() -> Dict[str, List[Dict[str, Any]]]:
        """
        Получает все доступные маршруты для пользователей.
        
        Returns:
            Dict[str, List[Dict]]: Словарь маршрутов по городам
        """
        try:
            # Начинаем со статических маршрутов сбора
            all_routes = AVAILABLE_ROUTES.copy()
            
            # Добавляем динамические маршруты доставки в Москву
            moscow_routes = await RouteSelector._get_moscow_delivery_routes()
            if moscow_routes:
                all_routes["Москва"] = moscow_routes
            
            return all_routes
            
        except Exception as e:
            logger.error(f"Ошибка при получении доступных маршрутов: {e}")
            # Возвращаем хотя бы статические маршруты
            return AVAILABLE_ROUTES.copy()
    
    
    @staticmethod
    async def _get_moscow_delivery_routes() -> List[Dict[str, Any]]:
        """
        Получает доступные маршруты доставки в Москву.
        
        Returns:
            List[Dict]: Список маршрутов доставки в Москву
        """
        try:
            async for session in get_session():
                # Получаем доступные маршруты в Москву
                query = select(MoscowRoute).where(
                    MoscowRoute.status == 'available'
                ).order_by(MoscowRoute.created_at.desc())
                
                result = await session.execute(query)
                moscow_routes = result.scalars().all()
                
                routes_list = []
                
                for route in moscow_routes:
                    # Получаем точки маршрута
                    points_query = select(MoscowRoutePoint).where(
                        MoscowRoutePoint.moscow_route_id == route.id
                    ).order_by(MoscowRoutePoint.order_index)
                    
                    points_result = await session.execute(points_query)
                    points = points_result.scalars().all()
                    
                    # Формируем данные о маршруте в формате, совместимом с AVAILABLE_ROUTES
                    for point in points:
                        routes_list.append({
                            "name": point.point_name,
                            "address": point.address,
                            "organization": point.organization,
                            "coordinates": None,  # Координаты для Москвы не обязательны
                            "moscow_route_id": route.id,
                            "moscow_route_name": route.route_name,
                            "containers_to_deliver": point.containers_to_deliver,
                            "route_type": "delivery",  # Тип маршрута: доставка
                            "moscow_point_id": point.id
                        })
                
                return routes_list
                
        except Exception as e:
            logger.error(f"Ошибка при получении маршрутов в Москву: {e}")
            return []
    
    
    @staticmethod
    def is_moscow_route(city_name: str) -> bool:
        """
        Проверяет, является ли маршрут маршрутом доставки в Москву.
        
        Args:
            city_name: Название города
            
        Returns:
            bool: True если это маршрут в Москву
        """
        return city_name == "Москва"
    
    
    @staticmethod
    def is_collection_route(city_name: str) -> bool:
        """
        Проверяет, является ли маршрут маршрутом сбора.
        
        Args:
            city_name: Название города
            
        Returns:
            bool: True если это маршрут сбора
        """
        return city_name in AVAILABLE_ROUTES
    
    
    @staticmethod
    async def get_route_info(city_name: str, route_points: List[Dict]) -> Dict[str, Any]:
        """
        Получает подробную информацию о маршруте.
        
        Args:
            city_name: Название города
            route_points: Точки маршрута
            
        Returns:
            Dict с информацией о маршруте
        """
        try:
            if RouteSelector.is_moscow_route(city_name):
                # Маршрут доставки в Москву
                total_containers = sum(point.get('containers_to_deliver', 0) for point in route_points)
                moscow_route_name = route_points[0].get('moscow_route_name', 'Неизвестный маршрут') if route_points else 'Пустой маршрут'
                
                return {
                    'type': 'delivery',
                    'city': city_name,
                    'route_name': moscow_route_name,
                    'points_count': len(route_points),
                    'total_containers': total_containers,
                    'description': f'Доставка {total_containers} контейнеров в {len(set(p["organization"] for p in route_points))} организаций',
                    'action_type': 'delivery'  # Тип действия: доставка (отдача контейнеров)
                }
            else:
                # Маршрут сбора
                return {
                    'type': 'collection',
                    'city': city_name,
                    'route_name': f'Сбор в {city_name}',
                    'points_count': len(route_points),
                    'total_containers': None,  # Количество будет определено в процессе
                    'description': f'Сбор контейнеров в {len(set(p["organization"] for p in route_points))} организациях',
                    'action_type': 'collection'  # Тип действия: сбор (получение контейнеров)
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении информации о маршруте: {e}")
            return {
                'type': 'unknown',
                'city': city_name,
                'route_name': f'Маршрут в {city_name}',
                'points_count': len(route_points),
                'total_containers': None,
                'description': 'Информация недоступна',
                'action_type': 'unknown'
            }
    
    
    @staticmethod
    async def get_moscow_route_by_id(route_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает маршрут в Москву по ID.
        
        Args:
            route_id: ID маршрута
            
        Returns:
            Dict с данными маршрута или None
        """
        try:
            async for session in get_session():
                query = select(MoscowRoute).where(MoscowRoute.id == route_id)
                result = await session.execute(query)
                moscow_route = result.scalar_one_or_none()
                
                if not moscow_route:
                    return None
                
                # Получаем точки маршрута
                points_query = select(MoscowRoutePoint).where(
                    MoscowRoutePoint.moscow_route_id == route_id
                ).order_by(MoscowRoutePoint.order_index)
                
                points_result = await session.execute(points_query)
                points = points_result.scalars().all()
                
                return {
                    'id': moscow_route.id,
                    'name': moscow_route.route_name,
                    'status': moscow_route.status,
                    'created_at': moscow_route.created_at,
                    'points': [
                        {
                            'id': point.id,
                            'organization': point.organization,
                            'point_name': point.point_name,
                            'address': point.address,
                            'contact_info': point.contact_info,
                            'containers_to_deliver': point.containers_to_deliver,
                            'containers_delivered': point.containers_delivered,
                            'order_index': point.order_index,
                            'status': point.status
                        }
                        for point in points
                    ]
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении маршрута в Москву по ID {route_id}: {e}")
            return None
