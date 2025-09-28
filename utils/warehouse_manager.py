"""
Менеджер склада в Ярославле для курьерского бота.

Содержит функции для:
- Расчета состояния склада по организациям
- Отслеживания входящих контейнеров из маршрутов
- Отслеживания исходящих контейнеров в Москву
- Формирования отчетов по складу
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy import select, and_, func, text
from sqlalchemy.orm import selectinload

from database.database import get_session
from database.models import Route, RouteProgress, Delivery, MoscowRoute, MoscowRoutePoint
from config import MOSCOW_DELIVERY_ADDRESSES

logger = logging.getLogger(__name__)


@dataclass
class WarehouseStock:
    """Класс для представления остатков на складе по организации."""
    organization: str
    total_incoming: int  # Всего привезено контейнеров
    total_outgoing: int  # Всего отправлено в Москву
    current_stock: int   # Текущий остаток на складе
    pending_delivery: int  # Ожидает отправки в Москву
    last_incoming_date: Optional[datetime] = None
    last_outgoing_date: Optional[datetime] = None


@dataclass
class WarehouseStats:
    """Класс для общей статистики склада."""
    total_stock: int
    organizations: List[WarehouseStock]
    last_updated: datetime
    total_incoming: int
    total_outgoing: int
    pending_deliveries: int


class WarehouseManager:
    """
    Менеджер склада в Ярославле.
    
    Отслеживает состояние склада по каждой организации:
    - Контейнеры, привезенные курьерами из маршрутов
    - Контейнеры, отправленные в Москву
    - Текущие остатки на складе
    """
    
    @staticmethod
    async def get_warehouse_status() -> WarehouseStats:
        """
        Получает текущее состояние склада в Ярославле.
        
        Returns:
            WarehouseStats: Полная статистика склада
        """
        try:
            async for session in get_session():
                # Получаем входящие контейнеры (из завершенных маршрутов СБОРА, исключая Москву)
                incoming_query = select(
                    Route.organization,
                    func.sum(RouteProgress.containers_count).label('total_containers'),
                    func.max(RouteProgress.visited_at).label('last_date')
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    )
                ).where(
                    and_(
                        RouteProgress.status == 'completed',
                        Route.city_name != 'Москва'  # Исключаем маршруты доставки в Москву
                    )
                ).group_by(Route.organization)
                
                incoming_result = await session.execute(incoming_query)
                incoming_data = incoming_result.fetchall()
                
                # Получаем исходящие контейнеры (отправленные в Москву)
                outgoing_query = select(
                    Delivery.organization,
                    func.sum(Delivery.total_containers).label('total_containers'),
                    func.max(Delivery.delivery_date).label('last_date')
                ).where(
                    Delivery.status.in_(['completed', 'in_progress'])
                ).group_by(Delivery.organization)
                
                outgoing_result = await session.execute(outgoing_query)
                outgoing_data = outgoing_result.fetchall()
                
                # Получаем ожидающие доставки
                pending_query = select(
                    Delivery.organization,
                    func.sum(Delivery.total_containers).label('pending_containers')
                ).where(
                    Delivery.status == 'pending'
                ).group_by(Delivery.organization)
                
                pending_result = await session.execute(pending_query)
                pending_data = pending_result.fetchall()
                
                # Преобразуем данные в словари для удобства
                incoming_dict = {row[0]: {'total': row[1], 'last_date': row[2]} for row in incoming_data}
                outgoing_dict = {row[0]: {'total': row[1], 'last_date': row[2]} for row in outgoing_data}
                pending_dict = {row[0]: row[1] for row in pending_data}
                
                # Получаем все уникальные организации
                all_organizations = set(incoming_dict.keys()) | set(outgoing_dict.keys()) | set(pending_dict.keys())
                
                # Формируем статистику по каждой организации
                organizations_stats = []
                total_stock = 0
                total_incoming = 0
                total_outgoing = 0
                total_pending = 0
                
                for org in sorted(all_organizations):
                    incoming = incoming_dict.get(org, {'total': 0, 'last_date': None})
                    outgoing = outgoing_dict.get(org, {'total': 0, 'last_date': None})
                    pending = pending_dict.get(org, 0)
                    
                    incoming_total = incoming['total'] or 0
                    outgoing_total = outgoing['total'] or 0
                    current_stock = incoming_total - outgoing_total
                    
                    org_stats = WarehouseStock(
                        organization=org,
                        total_incoming=incoming_total,
                        total_outgoing=outgoing_total,
                        current_stock=current_stock,
                        pending_delivery=pending,
                        last_incoming_date=incoming['last_date'],
                        last_outgoing_date=outgoing['last_date']
                    )
                    
                    organizations_stats.append(org_stats)
                    total_stock += current_stock
                    total_incoming += incoming_total
                    total_outgoing += outgoing_total
                    total_pending += pending
                
                return WarehouseStats(
                    total_stock=total_stock,
                    organizations=organizations_stats,
                    last_updated=datetime.now(),
                    total_incoming=total_incoming,
                    total_outgoing=total_outgoing,
                    pending_deliveries=total_pending
                )
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики склада: {e}")
            raise


    @staticmethod
    async def get_incoming_containers_by_period(days: int = 7) -> Dict[str, Any]:
        """
        Получает статистику входящих контейнеров за период.
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict с данными о поступлениях
        """
        try:
            async for session in get_session():
                cutoff_date = datetime.now() - timedelta(days=days)
                
                query = select(
                    Route.organization,
                    Route.city_name,
                    func.sum(RouteProgress.containers_count).label('containers'),
                    func.count(RouteProgress.id).label('routes_count'),
                    func.max(RouteProgress.visited_at).label('last_visit')
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    )
                ).where(
                    and_(
                        RouteProgress.status == 'completed',
                        RouteProgress.visited_at >= cutoff_date,
                        Route.city_name != 'Москва'  # Исключаем маршруты доставки в Москву
                    )
                ).group_by(Route.organization, Route.city_name)
                
                result = await session.execute(query)
                data = result.fetchall()
                
                # Группируем по организациям
                org_data = {}
                for row in data:
                    org, city, containers, routes, last_visit = row
                    if org not in org_data:
                        org_data[org] = {
                            'total_containers': 0,
                            'total_routes': 0,
                            'cities': {},
                            'last_visit': None
                        }
                    
                    org_data[org]['total_containers'] += containers
                    org_data[org]['total_routes'] += routes
                    org_data[org]['cities'][city] = {
                        'containers': containers,
                        'routes': routes
                    }
                    
                    if not org_data[org]['last_visit'] or last_visit > org_data[org]['last_visit']:
                        org_data[org]['last_visit'] = last_visit
                
                return {
                    'period_days': days,
                    'organizations': org_data,
                    'total_containers': sum(org['total_containers'] for org in org_data.values()),
                    'total_routes': sum(org['total_routes'] for org in org_data.values())
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики поступлений: {e}")
            raise


    @staticmethod
    async def get_outgoing_deliveries_by_period(days: int = 7) -> Dict[str, Any]:
        """
        Получает статистику исходящих доставок за период.
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict с данными об отправках
        """
        try:
            async for session in get_session():
                cutoff_date = datetime.now() - timedelta(days=days)
                
                query = select(
                    Delivery.organization,
                    Delivery.status,
                    func.sum(Delivery.total_containers).label('containers'),
                    func.count(Delivery.id).label('deliveries_count'),
                    func.max(Delivery.delivery_date).label('last_delivery')
                ).where(
                    Delivery.delivery_date >= cutoff_date
                ).group_by(Delivery.organization, Delivery.status)
                
                result = await session.execute(query)
                data = result.fetchall()
                
                # Группируем по организациям
                org_data = {}
                for row in data:
                    org, status, containers, deliveries, last_delivery = row
                    if org not in org_data:
                        org_data[org] = {
                            'total_containers': 0,
                            'total_deliveries': 0,
                            'by_status': {},
                            'last_delivery': None
                        }
                    
                    org_data[org]['total_containers'] += containers
                    org_data[org]['total_deliveries'] += deliveries
                    org_data[org]['by_status'][status] = {
                        'containers': containers,
                        'deliveries': deliveries
                    }
                    
                    if not org_data[org]['last_delivery'] or last_delivery > org_data[org]['last_delivery']:
                        org_data[org]['last_delivery'] = last_delivery
                
                return {
                    'period_days': days,
                    'organizations': org_data,
                    'total_containers': sum(org['total_containers'] for org in org_data.values()),
                    'total_deliveries': sum(org['total_deliveries'] for org in org_data.values())
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики отправок: {e}")
            raise


    @staticmethod
    def format_warehouse_status_message(warehouse_stats: WarehouseStats) -> str:
        """
        Форматирует статистику склада в текстовое сообщение.
        
        Args:
            warehouse_stats: Статистика склада
            
        Returns:
            str: Отформатированное сообщение
        """
        message = "🏢 <b>СКЛАД ЯРОСЛАВЛЬ</b>\n"
        message += f"📊 Состояние на {warehouse_stats.last_updated.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        # Общая информация
        message += "📦 <b>ОБЩАЯ СТАТИСТИКА:</b>\n"
        message += f"└ На складе: <b>{warehouse_stats.total_stock}</b> контейнеров\n"
        message += f"└ Всего поступило: {warehouse_stats.total_incoming} контейнеров\n"
        message += f"└ Всего отправлено: {warehouse_stats.total_outgoing} контейнеров\n"
        message += f"└ Ожидает отправки: {warehouse_stats.pending_deliveries} контейнеров\n\n"
        
        # По организациям
        if warehouse_stats.organizations:
            message += "🏥 <b>ПО ЛАБОРАТОРИЯМ:</b>\n\n"
            
            for org_stats in warehouse_stats.organizations:
                # Эмодзи для статуса
                if org_stats.current_stock == 0:
                    status_emoji = "✅"  # Все отправлено
                elif org_stats.current_stock > 20:
                    status_emoji = "🔴"  # Много на складе
                elif org_stats.current_stock > 10:
                    status_emoji = "🟡"  # Среднее количество
                else:
                    status_emoji = "🟢"  # Небольшое количество
                
                message += f"{status_emoji} <b>{org_stats.organization}:</b>\n"
                message += f"   💼 На складе: <b>{org_stats.current_stock}</b> контейнеров\n"
                message += f"   📥 Всего поступило: {org_stats.total_incoming}\n"
                message += f"   📤 Отправлено: {org_stats.total_outgoing}\n"
                
                if org_stats.pending_delivery > 0:
                    message += f"   ⏳ Ожидает отправки: {org_stats.pending_delivery}\n"
                
                # Адрес доставки в Москве
                moscow_address = MOSCOW_DELIVERY_ADDRESSES.get(org_stats.organization, {})
                if moscow_address:
                    message += f"   🏠 Адрес в Москве: {moscow_address.get('address', 'Не указан')}\n"
                
                # Даты последних операций
                if org_stats.last_incoming_date:
                    message += f"   📅 Последнее поступление: {org_stats.last_incoming_date.strftime('%d.%m.%Y %H:%M')}\n"
                if org_stats.last_outgoing_date:
                    message += f"   📅 Последняя отправка: {org_stats.last_outgoing_date.strftime('%d.%m.%Y %H:%M')}\n"
                
                message += "\n"
        else:
            message += "📭 <b>Склад пуст</b>\n"
        
        # Рекомендации
        if warehouse_stats.total_stock > 50:
            message += "💡 <b>РЕКОМЕНДАЦИЯ:</b> Много контейнеров на складе. Рекомендуется организовать доставку в Москву.\n"
        elif warehouse_stats.pending_deliveries > 0:
            message += "💡 <b>ВНИМАНИЕ:</b> Есть ожидающие доставки в Москву.\n"
        
        return message


    @staticmethod
    def format_period_summary_message(incoming_data: Dict[str, Any], outgoing_data: Dict[str, Any]) -> str:
        """
        Форматирует сводку за период.
        
        Args:
            incoming_data: Данные о поступлениях
            outgoing_data: Данные об отправках
            
        Returns:
            str: Отформатированное сообщение
        """
        days = incoming_data.get('period_days', 7)
        message = f"📈 <b>ДИНАМИКА СКЛАДА ЗА {days} ДНЕЙ</b>\n\n"
        
        # Поступления
        message += "📥 <b>ПОСТУПЛЕНИЯ:</b>\n"
        message += f"└ Всего контейнеров: {incoming_data.get('total_containers', 0)}\n"
        message += f"└ Маршрутов завершено: {incoming_data.get('total_routes', 0)}\n\n"
        
        for org, data in incoming_data.get('organizations', {}).items():
            message += f"🔹 <b>{org}:</b> {data['total_containers']} контейнеров ({data['total_routes']} маршрутов)\n"
            for city, city_data in data['cities'].items():
                message += f"   └ {city}: {city_data['containers']} контейнеров\n"
        
        message += "\n"
        
        # Отправки
        message += "📤 <b>ОТПРАВКИ В МОСКВУ:</b>\n"
        message += f"└ Всего контейнеров: {outgoing_data.get('total_containers', 0)}\n"
        message += f"└ Доставок: {outgoing_data.get('total_deliveries', 0)}\n\n"
        
        for org, data in outgoing_data.get('organizations', {}).items():
            message += f"🔹 <b>{org}:</b> {data['total_containers']} контейнеров ({data['total_deliveries']} доставок)\n"
            for status, status_data in data['by_status'].items():
                status_emoji = {"pending": "⏳", "in_progress": "🚚", "completed": "✅"}.get(status, "❓")
                message += f"   └ {status_emoji} {status}: {status_data['containers']} контейнеров\n"
        
        # Баланс
        balance = incoming_data.get('total_containers', 0) - outgoing_data.get('total_containers', 0)
        message += f"\n⚖️ <b>БАЛАНС:</b> {'+' if balance >= 0 else ''}{balance} контейнеров\n"
        
        if balance > 0:
            message += "📈 Склад пополняется\n"
        elif balance < 0:
            message += "📉 Склад разгружается\n"
        else:
            message += "⚖️ Склад в балансе\n"
        
        return message


    @staticmethod
    async def create_moscow_route(admin_id: int) -> Dict[str, Any]:
        """
        Создает маршрут в Москву на основе текущего состояния склада.
        
        Args:
            admin_id: ID администратора, создающего маршрут
            
        Returns:
            Dict с информацией о созданном маршруте
        """
        async for session in get_session():
            try:
                # Получаем текущие остатки на складе внутри той же сессии
                # Получаем входящие контейнеры (из завершенных маршрутов СБОРА, исключая Москву)
                incoming_query = select(
                    Route.organization,
                    func.sum(RouteProgress.containers_count).label('total_containers')
                ).select_from(
                    RouteProgress.__table__.join(
                        Route.__table__,
                        RouteProgress.route_id == Route.id
                    )
                ).where(
                    and_(
                        RouteProgress.status == 'completed',
                        Route.city_name != 'Москва'  # Исключаем маршруты доставки в Москву
                    )
                ).group_by(Route.organization)
                
                incoming_result = await session.execute(incoming_query)
                incoming_data = incoming_result.fetchall()
                
                # Получаем исходящие контейнеры (отправленные в Москву)
                outgoing_query = select(
                    Delivery.organization,
                    func.sum(Delivery.total_containers).label('total_containers')
                ).where(
                    Delivery.status.in_(['completed', 'in_progress'])
                ).group_by(Delivery.organization)
                
                outgoing_result = await session.execute(outgoing_query)
                outgoing_data = outgoing_result.fetchall()
                
                # Преобразуем данные в словари для удобства
                incoming_dict = {row[0]: row[1] for row in incoming_data}
                outgoing_dict = {row[0]: row[1] for row in outgoing_data}
                
                # Получаем все уникальные организации
                all_organizations = set(incoming_dict.keys()) | set(outgoing_dict.keys())
                
                # Формируем статистику по каждой организации
                organizations_with_stock = []
                total_stock = 0
                
                for org in sorted(all_organizations):
                    incoming_total = incoming_dict.get(org, 0)
                    outgoing_total = outgoing_dict.get(org, 0)
                    current_stock = incoming_total - outgoing_total
                    
                    if current_stock > 0:
                        organizations_with_stock.append({
                            'organization': org,
                            'current_stock': current_stock
                        })
                        total_stock += current_stock
                
                # Проверяем, есть ли контейнеры на складе
                if total_stock == 0:
                    return {
                        'success': False,
                        'message': 'На складе нет контейнеров для отправки в Москву'
                    }
                
                # Создаем название маршрута
                route_name = f"Доставка в Москву {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                
                # Создаем маршрут
                moscow_route = MoscowRoute(
                    route_name=route_name,
                    status='available',
                    created_by_admin=admin_id
                )
                session.add(moscow_route)
                await session.flush()  # Получаем ID маршрута
                
                # Проверяем, что ID получен
                if not moscow_route.id:
                    raise Exception("Не удалось получить ID созданного маршрута")
                
                # Создаем точки маршрута для каждой организации
                order_index = 0
                total_containers = 0
                created_points = []
                
                for org_data in organizations_with_stock:
                    # Получаем адрес в Москве
                    moscow_address = MOSCOW_DELIVERY_ADDRESSES.get(org_data['organization'], {})
                    
                    route_point = MoscowRoutePoint(
                        moscow_route_id=moscow_route.id,
                        organization=org_data['organization'],
                        point_name=f"{org_data['organization']} Москва",
                        address=moscow_address.get('address', 'Адрес не указан'),
                        contact_info=moscow_address.get('contact', 'Контакт не указан'),
                        containers_to_deliver=org_data['current_stock'],
                        order_index=order_index,
                        status='pending'
                    )
                    session.add(route_point)
                    
                    created_points.append({
                        'organization': org_data['organization'],
                        'containers': org_data['current_stock'],
                        'address': moscow_address.get('address', 'Адрес не указан')
                    })
                    
                    total_containers += org_data['current_stock']
                    order_index += 1
                
                await session.commit()
                
                return {
                    'success': True,
                    'route_id': moscow_route.id,
                    'route_name': route_name,
                    'total_containers': total_containers,
                    'points_created': len(created_points),
                    'points': created_points,
                    'message': f'Маршрут "{route_name}" успешно создан'
                }
            
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при создании маршрута в Москву: {e}")
                return {
                    'success': False,
                    'message': f'Ошибка при создании маршрута: {str(e)}'
                }


    @staticmethod
    async def get_available_moscow_routes() -> List[Dict[str, Any]]:
        """
        Получает список доступных маршрутов в Москву.
        
        Returns:
            List[Dict]: Список доступных маршрутов
        """
        try:
            async for session in get_session():
                query = select(MoscowRoute).where(
                    MoscowRoute.status == 'available'
                ).order_by(MoscowRoute.created_at.desc())
                
                result = await session.execute(query)
                routes = result.scalars().all()
                
                route_list = []
                for route in routes:
                    # Получаем информацию о точках маршрута
                    points_query = select(MoscowRoutePoint).where(
                        MoscowRoutePoint.moscow_route_id == route.id
                    ).order_by(MoscowRoutePoint.order_index)
                    
                    points_result = await session.execute(points_query)
                    points = points_result.scalars().all()
                    
                    total_containers = sum(point.containers_to_deliver for point in points)
                    
                    route_list.append({
                        'id': route.id,
                        'name': route.route_name,
                        'status': route.status,
                        'created_at': route.created_at,
                        'total_containers': total_containers,
                        'points_count': len(points),
                        'points': [
                            {
                                'organization': point.organization,
                                'containers': point.containers_to_deliver,
                                'address': point.address
                            }
                            for point in points
                        ]
                    })
                
                return route_list
                
        except Exception as e:
            logger.error(f"Ошибка при получении маршрутов в Москву: {e}")
            return []


    @staticmethod
    async def clear_warehouse_after_route_creation() -> bool:
        """
        Обнуляет склад после создания маршрута в Москву.
        
        Помечает все контейнеры как отправленные в маршрут (статус 'in_progress').
        Они будут помечены как 'completed' только после фактической доставки.
        
        Returns:
            bool: Успешность операции
        """
        try:
            async for session in get_session():
                # Получаем все ожидающие доставки и помечаем их как отправленные в маршрут
                pending_deliveries = await session.scalars(
                    select(Delivery).where(Delivery.status == 'pending')
                )
                pending_list = pending_deliveries.all()
                
                updated_count = 0
                for delivery in pending_list:
                    delivery.status = 'in_progress'
                    updated_count += 1
                
                await session.commit()
                
                logger.info(f"Склад обнулен: {updated_count} pending доставок переведены в in_progress")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при очистке склада: {e}")
            return False


    @staticmethod
    def format_moscow_route_creation_message(route_info: Dict[str, Any]) -> str:
        """
        Форматирует сообщение о создании маршрута в Москву.
        
        Args:
            route_info: Информация о созданном маршруте
            
        Returns:
            str: Отформатированное сообщение
        """
        if not route_info['success']:
            return f"❌ {route_info['message']}"
        
        message = "✅ <b>МАРШРУТ В МОСКВУ СОЗДАН!</b>\n\n"
        message += f"🚚 <b>Название:</b> {route_info['route_name']}\n"
        message += f"📦 <b>Всего контейнеров:</b> {route_info['total_containers']}\n"
        message += f"📍 <b>Точек доставки:</b> {route_info['points_created']}\n\n"
        
        message += "🏥 <b>ТОЧКИ МАРШРУТА:</b>\n"
        for i, point in enumerate(route_info['points'], 1):
            message += f"{i}. <b>{point['organization']}</b>\n"
            message += f"   📦 Контейнеров: {point['containers']}\n"
            message += f"   📍 Адрес: {point['address']}\n\n"
        
        message += "🏢 <b>СКЛАД ЯРОСЛАВЛЬ:</b>\n"
        message += "├ Все контейнеры переданы в маршрут\n"
        message += "└ Склад обнулен\n\n"
        
        message += "👥 <b>ДОСТУПНОСТЬ:</b>\n"
        message += "├ Маршрут появился в списке \"Выбрать маршрут\"\n"
        message += "└ Курьеры могут выбрать его для выполнения\n\n"
        
        message += "💡 <b>Теперь курьер может выбрать этот маршрут и доставить контейнеры в Москву!</b>"
        
        return message
