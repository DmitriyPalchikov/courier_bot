"""
Административные обработчики для управления курьерским ботом.

Этот модуль содержит функции для администраторов системы:
- Просмотр статистики и отчётов
- Управление пользователями
- Формирование маршрутных листов в Москву
- Мониторинг активных маршрутов

Доступ к административным функциям имеют только пользователи
из списка ADMIN_IDS в конфигурации.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload

# Импорты наших модулей
from database.database import get_session
from database.models import User, Route, RouteProgress, Delivery
from states.user_states import AdminStates
from config import ADMIN_IDS, MOSCOW_DELIVERY_ADDRESSES
from keyboards.admin_keyboards import (
    get_admin_menu_keyboard,
    get_deliveries_keyboard,
    get_statistics_keyboard
)

# Создаём роутер для административных обработчиков
admin_router = Router(name='admin_router')

# Настраиваем логирование
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        bool: True если пользователь админ, False иначе
    """
    return user_id in ADMIN_IDS


@admin_router.message(Command('admin'))
async def cmd_admin(message: Message) -> None:
    """
    Обработчик команды /admin - вход в административную панель.
    
    Проверяет права доступа и отображает меню администратора.
    
    Args:
        message: Объект сообщения от пользователя
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await message.answer(
        "🔧 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_menu_keyboard()
    )


@admin_router.callback_query(F.data == "admin_statistics")
async def show_statistics(callback: CallbackQuery) -> None:
    """
    Показывает общую статистику работы бота.
    
    Args:
        callback: Объект callback query от кнопки статистики
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    async for session in get_session():
        # Общее количество пользователей
        users_count = await session.scalar(select(func.count(User.telegram_id)))
        
        # Активные пользователи за последние 7 дней
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_users = await session.scalar(
            select(func.count(User.telegram_id.distinct())).select_from(
                User.__table__.join(RouteProgress.__table__)
            ).where(RouteProgress.visited_at >= week_ago)
        )
        
        # Всего маршрутов пройдено
        total_routes = await session.scalar(
            select(func.count(RouteProgress.id))
        )
        
        # Всего коробок собрано
        total_boxes = await session.scalar(
            select(func.sum(RouteProgress.boxes_count))
        ) or 0
        
        # Статистика по организациям
        org_stats = await session.execute(
            select(
                Route.organization,
                func.sum(RouteProgress.boxes_count).label('total_boxes'),
                func.count(RouteProgress.id).label('total_visits')
            )
            .join(RouteProgress)
            .group_by(Route.organization)
            .order_by(desc('total_boxes'))
        )
        
        org_data = org_stats.all()
        
        # Pending доставки
        pending_deliveries = await session.scalar(
            select(func.count(Delivery.id)).where(Delivery.status == 'pending')
        )
    
    # Формируем сообщение со статистикой
    stats_text = (
        f"📊 <b>Статистика системы</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего зарегистрировано: {users_count}\n"
        f"• Активны за неделю: {active_users or 0}\n\n"
        f"📦 <b>Сборы товаров:</b>\n"
        f"• Всего маршрутов: {total_routes or 0}\n"
        f"• Всего коробок собрано: {total_boxes}\n\n"
        f"🏢 <b>По организациям:</b>\n"
    )
    
    for org_row in org_data:
        stats_text += f"• {org_row.organization}: {org_row.total_boxes} коробок ({org_row.total_visits} посещений)\n"
    
    stats_text += f"\n🚚 <b>Доставки в Москву:</b>\n"
    stats_text += f"• Ожидают отправки: {pending_deliveries or 0}"
    
    await callback.message.edit_text(
        text=stats_text,
        reply_markup=get_statistics_keyboard()
    )
    
    await callback.answer()


@admin_router.callback_query(F.data == "admin_deliveries")
async def show_deliveries(callback: CallbackQuery) -> None:
    """
    Показывает список доставок, готовых к отправке в Москву.
    
    Args:
        callback: Объект callback query от кнопки доставок
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    async for session in get_session():
        # Получаем pending доставки
        stmt = select(Delivery).where(
            Delivery.status == 'pending'
        ).order_by(Delivery.created_at.desc())
        
        deliveries = await session.scalars(stmt)
        deliveries_list = deliveries.all()
    
    if not deliveries_list:
        await callback.message.edit_text(
            "📭 Нет доставок, ожидающих отправки",
            reply_markup=get_admin_menu_keyboard()
        )
        await callback.answer()
        return
    
    # Группируем доставки по организациям
    org_deliveries = {}
    for delivery in deliveries_list:
        org = delivery.organization
        if org not in org_deliveries:
            org_deliveries[org] = {
                'total_boxes': 0,
                'deliveries_count': 0,
                'addresses': set()
            }
        
        org_deliveries[org]['total_boxes'] += delivery.total_boxes
        org_deliveries[org]['deliveries_count'] += 1
        org_deliveries[org]['addresses'].add(delivery.delivery_address)
    
    # Формируем маршрутный лист
    deliveries_text = (
        f"🚚 <b>Маршрутный лист в Москву</b>\n"
        f"📅 Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    )
    
    total_all_boxes = 0
    for org, data in org_deliveries.items():
        total_all_boxes += data['total_boxes']
        
        deliveries_text += (
            f"🏢 <b>{org}</b>\n"
            f"📦 Коробок: {data['total_boxes']}\n"
            f"📍 Адрес: {MOSCOW_DELIVERY_ADDRESSES.get(org, {}).get('address', 'Не указан')}\n"
            f"📞 Контакт: {MOSCOW_DELIVERY_ADDRESSES.get(org, {}).get('contact', 'Не указан')}\n"
            f"🕐 Время работы: {MOSCOW_DELIVERY_ADDRESSES.get(org, {}).get('working_hours', 'Не указано')}\n\n"
        )
    
    deliveries_text += f"📊 <b>Итого коробок: {total_all_boxes}</b>"
    
    await callback.message.edit_text(
        text=deliveries_text,
        reply_markup=get_deliveries_keyboard()
    )
    
    await callback.answer()


@admin_router.callback_query(F.data == "confirm_deliveries")
async def confirm_deliveries(callback: CallbackQuery) -> None:
    """
    Подтверждает формирование доставок и меняет их статус.
    
    Args:
        callback: Объект callback query от кнопки подтверждения
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    async for session in get_session():
        # Обновляем статус всех pending доставок
        stmt = select(Delivery).where(Delivery.status == 'pending')
        deliveries = await session.scalars(stmt)
        
        updated_count = 0
        for delivery in deliveries:
            delivery.status = 'confirmed'
            updated_count += 1
        
        await session.commit()
    
    await callback.message.edit_text(
        f"✅ <b>Доставки подтверждены!</b>\n\n"
        f"Обновлено записей: {updated_count}\n"
        f"Статус изменён на 'confirmed'\n\n"
        f"Маршрутный лист готов для печати.",
        reply_markup=get_admin_menu_keyboard()
    )
    
    await callback.answer("Доставки подтверждены!")


@admin_router.callback_query(F.data == "admin_users")
async def show_users(callback: CallbackQuery) -> None:
    """
    Показывает список пользователей системы.
    
    Args:
        callback: Объект callback query от кнопки пользователей
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    async for session in get_session():
        # Получаем пользователей с их статистикой
        stmt = select(
            User.telegram_id,
            User.username,
            User.full_name,
            User.is_active,
            User.created_at,
            func.count(RouteProgress.id).label('routes_count'),
            func.sum(RouteProgress.boxes_count).label('total_boxes')
        ).outerjoin(RouteProgress).group_by(
            User.telegram_id
        ).order_by(User.created_at.desc()).limit(20)
        
        users_data = await session.execute(stmt)
        users_list = users_data.all()
    
    if not users_list:
        await callback.message.edit_text(
            "👥 Пользователей не найдено",
            reply_markup=get_admin_menu_keyboard()
        )
        await callback.answer()
        return
    
    # Формируем список пользователей
    users_text = "👥 <b>Пользователи системы</b>\n\n"
    
    for user_data in users_list[:10]:  # Показываем первых 10
        status = "🟢" if user_data.is_active else "🔴"
        username = f"@{user_data.username}" if user_data.username else "Без username"
        
        users_text += (
            f"{status} <b>{user_data.full_name or 'Без имени'}</b>\n"
            f"ID: {user_data.telegram_id}\n"
            f"Username: {username}\n"
            f"Маршрутов: {user_data.routes_count or 0}\n"
            f"Коробок: {user_data.total_boxes or 0}\n"
            f"Регистрация: {user_data.created_at.strftime('%d.%m.%Y')}\n\n"
        )
    
    await callback.message.edit_text(
        text=users_text,
        reply_markup=get_admin_menu_keyboard()
    )
    
    await callback.answer()


# Возврат в меню администратора
@admin_router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery) -> None:
    """
    Возврат в главное меню администратора.
    
    Args:
        callback: Объект callback query
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_menu_keyboard()
    )
    
    await callback.answer()
