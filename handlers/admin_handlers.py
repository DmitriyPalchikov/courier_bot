"""
Обработчики административных команд и действий.

Этот модуль содержит все обработчики для административного
интерфейса бота, включая просмотр статистики, управление
пользователями и настройки системы.
"""

import logging

import os
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from database.database import get_session
from database.models import User, Route, RouteProgress, Delivery
from sqlalchemy import select, and_
from keyboards.admin_keyboards import (
    get_admin_menu_keyboard,
    get_statistics_keyboard,
    get_export_keyboard,
    get_settings_keyboard,
    get_period_selection_keyboard,
    get_warehouse_keyboard,
    get_routes_monitoring_keyboard,
    get_route_details_keyboard,
    get_city_selection_keyboard,
    get_admin_route_selection_keyboard,
    get_admin_route_detail_keyboard,
    get_admin_photos_viewer_keyboard
)
from utils.statistics import (
    get_route_statistics,
    get_user_performance,
    get_busiest_days,
    format_statistics_message
)
from utils.report_generator import generate_excel_report, generate_pdf_report
from utils.warehouse_manager import WarehouseManager
from utils.route_monitor import RouteMonitor
from config import ADMIN_IDS

# Создаём роутер для админских хендлеров
admin_router = Router(name='admin_router')

# Настраиваем логирование
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in ADMIN_IDS


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """
    Обработчик команды /admin.
    
    Показывает административное меню, если пользователь является админом.
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        "👨‍💼 Панель администратора\n\n"
        "Выберите нужный раздел:",
        reply_markup=get_admin_menu_keyboard()
    )


@admin_router.message(F.text == "📊 Статистика")
async def show_statistics_menu(message: Message) -> None:
    """Показывает меню статистики."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    await message.answer(
        "📊 Статистика\n\n"
        "Выберите тип статистики:",
        reply_markup=get_statistics_keyboard()
    )


@admin_router.callback_query(F.data.startswith("stats_"))
async def process_statistics_callback(callback: CallbackQuery) -> None:
    """Обрабатывает нажатия кнопок в меню статистики."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    action = callback.data.split("_")[1]
    
    async for session in get_session():
        if action == "general":
            # Получаем общую статистику
            stats = await get_route_statistics(session)
            message = format_statistics_message(stats)
            await callback.message.edit_text(
                message,
                reply_markup=get_statistics_keyboard()
            )
            
        elif action == "couriers":
            # Получаем статистику курьеров
            performers = await get_user_performance(session, limit=10)
            
            message = "👥 <b>Топ курьеров:</b>\n\n"
            for i, user in enumerate(performers, 1):
                message += (
                    f"{i}. @{user['username']}\n"
                    f"📦 Контейнеров: {user['total_containers']}\n"
                    f"🚚 Маршрутов: {user['total_routes']}\n"
                    f"📊 Среднее: {user['avg_boxes_per_route']:.1f} контейнеров/маршрут\n\n"
                )
            
            await callback.message.edit_text(
                message,
                reply_markup=get_statistics_keyboard()
            )
            
        elif action in ["today", "week", "month"]:
            # Определяем период
            days = {
                "today": 1,
                "week": 7,
                "month": 30
            }[action]
            
            # Получаем статистику за период
            stats = await get_route_statistics(session, days=days)
            busiest = await get_busiest_days(session, days=days, limit=5)
            
            message = format_statistics_message(stats)
            message += "\n\n📅 <b>Самые загруженные дни:</b>\n"
            
            for day in busiest:
                message += (
                    f"\n{day['date']}:\n"
                    f"🚚 Маршрутов: {day['total_routes']}\n"
                    f"📦 Контейнеров: {day['total_containers']}\n"
                )
            
            await callback.message.edit_text(
                message,
                reply_markup=get_statistics_keyboard()
            )
            
        elif action == "routes":
            # Обработка callback_data "stats_routes_monitoring"
            if callback.data == "stats_routes_monitoring":
                logger.info(f"🛣️ МОНИТОРИНГ МАРШРУТОВ: Вызван пользователем {callback.from_user.id}")
                await callback.message.edit_text(
                    "🛣️ <b>МОНИТОРИНГ МАРШРУТОВ</b>\n\n"
                    "Выберите тип маршрутов для просмотра:",
                    reply_markup=get_routes_monitoring_keyboard()
                )
                return
        
        elif action == "refresh":
            # Просто повторно показываем общую статистику
            stats = await get_route_statistics(session)
            message = format_statistics_message(stats)
            await callback.message.edit_text(
                message,
                reply_markup=get_statistics_keyboard()
            )
            
        elif action == "close":
            # Удаляем сообщение со статистикой
            await callback.message.delete()
    
    await callback.answer()


@admin_router.message(F.text == "📥 Экспорт отчетов")
async def show_export_menu(message: Message) -> None:
    """Показывает меню экспорта отчетов."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    await message.answer(
        "📥 Экспорт отчетов\n\n"
        "Выберите формат отчета:",
        reply_markup=get_export_keyboard()
    )


@admin_router.callback_query(F.data.startswith("export_"))
async def process_export_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает нажатия кнопок в меню экспорта."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    action = callback.data.split("_")[1]
    
    if action == "select_period":
        await callback.message.edit_text(
            "📅 Выберите период для отчета:",
            reply_markup=get_period_selection_keyboard()
        )
    
    elif action in ["excel", "pdf"]:
        # Получаем данные о периоде из состояния
        data = await state.get_data()
        start_date = data.get('report_start_date')
        end_date = data.get('report_end_date')
        
        # Конвертируем строки в даты если они есть
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        
        try:
            # Отправляем сообщение о начале генерации
            progress_message = await callback.message.answer(
                "⏳ Генерация отчета..."
            )
            
            # Генерируем отчет
            async for session in get_session():
                if action == "excel":
                    filepath = await generate_excel_report(
                        session,
                        start_date=start_date,
                        end_date=end_date
                    )
                else:  # pdf
                    filepath = await generate_pdf_report(
                        session,
                        start_date=start_date,
                        end_date=end_date
                    )
            
            # Отправляем файл
            file = FSInputFile(filepath)
            await bot.send_document(
                chat_id=callback.from_user.id,
                document=file,
                caption="📊 Ваш отчет готов!"
            )
            
            # Удаляем файл после отправки
            os.remove(filepath)
            
            # Удаляем сообщение о прогрессе
            await progress_message.delete()
            
        except ImportError:
            await callback.answer(
                "❌ Библиотеки для генерации отчетов не установлены. Установите: pip install openpyxl reportlab pandas",
                show_alert=True
            )
            return
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            await callback.answer(
                "❌ Произошла ошибка при генерации отчета",
                show_alert=True
            )
            return
    
    elif action == "close":
        await callback.message.delete()
    
    await callback.answer()


@admin_router.message(F.text == "⚙️ Настройки")
async def show_settings_menu(message: Message) -> None:
    """Показывает меню настроек."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    await message.answer(
        "⚙️ Настройки\n\n"
        "Выберите раздел настроек:",
        reply_markup=get_settings_keyboard()
    )


@admin_router.callback_query(F.data.startswith("period_"))
async def process_period_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор периода для отчета."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    action = callback.data.split("_")[1]
    
    # Определяем даты на основе выбранного периода
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if action == "today":
        start_date = today
        end_date = today + timedelta(days=1)
    elif action == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = today
    elif action == "week":
        start_date = today - timedelta(days=7)
        end_date = today + timedelta(days=1)
    elif action == "month":
        start_date = today - timedelta(days=30)
        end_date = today + timedelta(days=1)
    elif action == "custom":
        # TODO: Реализовать выбор произвольного периода
        await callback.answer(
            "🚧 Выбор произвольного периода в разработке",
            show_alert=True
        )
        return
    elif action == "cancel":
        await state.update_data(report_start_date=None, report_end_date=None)
        await callback.message.edit_text(
            "📥 Экспорт отчетов\n\n"
            "Выберите формат отчета:",
            reply_markup=get_export_keyboard()
        )
        await callback.answer()
        return
    else:
        await callback.answer("❌ Неизвестное действие", show_alert=True)
        return
    
    # Сохраняем выбранный период в состояние
    await state.update_data(
        report_start_date=start_date.isoformat(),
        report_end_date=end_date.isoformat()
    )
    
    # Показываем меню экспорта с информацией о выбранном периоде
    period_info = f"с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}"
    await callback.message.edit_text(
        f"📥 Экспорт отчетов\n\n"
        f"📅 Выбранный период: {period_info}\n\n"
        f"Выберите формат отчета:",
        reply_markup=get_export_keyboard()
    )
    
    await callback.answer()


@admin_router.callback_query(F.data.startswith("settings_"))
async def process_settings_callback(callback: CallbackQuery) -> None:
    """Обрабатывает нажатия кнопок в меню настроек."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    action = callback.data.split("_")[1]
    
    if action in ["couriers", "routes"]:
        await callback.answer(
            "🚧 Этот раздел находится в разработке",
            show_alert=True
        )
    
    elif action == "backup":
        # Создаем директорию для бэкапов если её нет
        os.makedirs("backups", exist_ok=True)
        
        # Создаем имя файла для бэкапа
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/courier_bot_{timestamp}.db"
        
        try:
            # Копируем файл базы данных
            import shutil
            shutil.copy2("courier_bot.db", backup_path)
            
            # Отправляем файл бэкапа
            file = FSInputFile(backup_path)
            await callback.message.answer_document(
                document=file,
                caption=f"📦 Резервная копия базы данных от {timestamp}"
            )
            
            # Удаляем временный файл
            os.remove(backup_path)
            
            await callback.answer(
                "✅ Резервная копия создана и отправлена",
                show_alert=True
            )
            
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии: {e}")
            await callback.answer(
                "❌ Ошибка при создании резервной копии",
                show_alert=True
            )
    
    elif action == "close":
        await callback.message.delete()
    
    await callback.answer()


@admin_router.message(F.text == "📋 Активные доставки")
async def show_active_deliveries(message: Message) -> None:
    """Показывает список активных доставок в Москву."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    async for session in get_session():
        # Получаем активные доставки
        deliveries = await session.execute(
            select(Delivery)
            .filter(Delivery.status.in_(['pending', 'in_progress']))
            .order_by(Delivery.delivery_date)
        )
        deliveries = deliveries.scalars().all()
        
        if not deliveries:
            await message.answer(
                "📭 Нет активных доставок в Москву",
                reply_markup=get_admin_menu_keyboard()
            )
            return
        
        # Формируем сообщение
        message_text = "📋 <b>Активные доставки в Москву:</b>\n\n"
        
        for delivery in deliveries:
            status_emoji = "🕒" if delivery.status == "pending" else "🚚"
            message_text += (
                f"{status_emoji} <b>Доставка #{delivery.id}</b>\n"
                f"📦 Организация: {delivery.organization}\n"
                f"📦 Контейнеров: {delivery.total_containers}\n"
                f"📍 Адрес: {delivery.delivery_address}\n"
                f"📱 Контакт: {delivery.contact_info}\n"
                f"📅 Дата: {delivery.delivery_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        await message.answer(
            message_text,
            reply_markup=get_admin_menu_keyboard()
        )


@admin_router.message(F.text == "🏢 Склад Ярославль")
async def show_warehouse_menu(message: Message) -> None:
    """Показывает меню склада в Ярославле."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    await message.answer(
        "🏢 <b>Склад Ярославль</b>\n\n"
        "Выберите информацию для просмотра:",
        reply_markup=get_warehouse_keyboard()
    )


@admin_router.callback_query(F.data.startswith("warehouse_"))
async def process_warehouse_callback(callback: CallbackQuery) -> None:
    """Обрабатывает нажатия кнопок в меню склада."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    # Получаем полное действие (все части после первого "_")
    parts = callback.data.split("_")
    if len(parts) >= 2:
        action = "_".join(parts[1:])  # Объединяем все части после "warehouse"
    else:
        action = callback.data
    
    try:
        if action == "status" or action == "refresh":
            # Показываем текущее состояние склада
            warehouse_stats = await WarehouseManager.get_warehouse_status()
            message = WarehouseManager.format_warehouse_status_message(warehouse_stats)
            
            await callback.message.edit_text(
                message,
                reply_markup=get_warehouse_keyboard()
            )
            
        elif action in ["today", "week", "month"]:
            # Показываем динамику за период
            days = {
                "today": 1,
                "week": 7,
                "month": 30
            }[action]
            
            # Получаем данные о поступлениях и отправках
            incoming_data = await WarehouseManager.get_incoming_containers_by_period(days)
            outgoing_data = await WarehouseManager.get_outgoing_deliveries_by_period(days)
            
            # Форматируем сообщение
            message = WarehouseManager.format_period_summary_message(incoming_data, outgoing_data)
            
            await callback.message.edit_text(
                message,
                reply_markup=get_warehouse_keyboard()
            )
            
        elif action == "create_moscow_route":
            # Создаем маршрут в Москву
            try:
                route_info = await WarehouseManager.create_moscow_route(callback.from_user.id)
                
                if route_info['success']:
                    # Очищаем склад после создания маршрута
                    await WarehouseManager.clear_warehouse_after_route_creation()
                
                # Форматируем и отправляем сообщение
                message = WarehouseManager.format_moscow_route_creation_message(route_info)
                
                await callback.message.edit_text(
                    message,
                    reply_markup=get_warehouse_keyboard()
                )
                
            except Exception as e:
                logger.error(f"Ошибка при создании маршрута в Москву: {e}")
                await callback.answer(
                    "❌ Произошла ошибка при создании маршрута",
                    show_alert=True
                )
                return
        
        elif action == "close":
            # Удаляем сообщение со складом
            await callback.message.delete()
            
        else:
            await callback.answer("❌ Неизвестное действие", show_alert=True)
            return
            
    except Exception as e:
        logger.error(f"Ошибка при обработке склада: {e}")
        await callback.answer(
            "❌ Произошла ошибка при получении данных склада",
            show_alert=True
        )
        return
    
    await callback.answer()


@admin_router.message(F.text == "🏠 Главное меню")
async def return_to_main_menu(message: Message) -> None:
    """Возвращает в главное меню бота."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    from keyboards.user_keyboards import get_main_menu_keyboard
    
    await message.answer(
        "🏠 Вы вернулись в главное меню",
        reply_markup=get_main_menu_keyboard()
    )


# ================================
# ОБРАБОТЧИКИ МОНИТОРИНГА МАРШРУТОВ
# ================================


@admin_router.callback_query(F.data == "routes_active")
async def show_active_routes(callback: CallbackQuery) -> None:
    """Показывает активные маршруты в виде списка для выбора."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.answer("🔄 Загружаю активные маршруты...")
    
    active_routes = await RouteMonitor.get_active_route_sessions()
    
    if not active_routes:
        await callback.message.edit_text(
            "🏃‍♂️ АКТИВНЫЕ МАРШРУТЫ\n\n"
            "❌ Активных маршрутов не найдено.",
            reply_markup=get_routes_monitoring_keyboard()
        )
        return
    
    message_text = f"🏃‍♂️ АКТИВНЫЕ МАРШРУТЫ ({len(active_routes)})\n\n"
    message_text += "Выберите маршрут для детального просмотра:"
    
    # Преобразуем данные в формат для клавиатуры
    routes_data = []
    for route in active_routes:
        routes_data.append({
            'route_id': route.session_id,
            'date': route.start_time.strftime('%d.%m'),
            'city': route.city_name,
            'username': route.username,
            'points_count': route.total_points,
            'total_containers': route.total_containers,
            'status': route.status
        })
    
    keyboard = get_admin_route_selection_keyboard(routes_data)
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data == "routes_completed")
async def show_completed_routes(callback: CallbackQuery) -> None:
    """Показывает завершенные маршруты в виде списка для выбора."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.answer("🔄 Загружаю завершенные маршруты...")
    
    completed_routes = await RouteMonitor.get_completed_route_sessions(days=7)
    
    if not completed_routes:
        await callback.message.edit_text(
            "✅ ЗАВЕРШЕННЫЕ МАРШРУТЫ\n\n"
            "❌ Завершенных маршрутов за последние 7 дней не найдено.",
            reply_markup=get_routes_monitoring_keyboard()
        )
        return
    
    message_text = f"✅ ЗАВЕРШЕННЫЕ МАРШРУТЫ ({len(completed_routes)})\n\n"
    message_text += "Выберите маршрут для детального просмотра:"
    
    # Преобразуем данные в формат для клавиатуры
    routes_data = []
    for route in completed_routes[:20]:  # Показываем первые 20
        routes_data.append({
            'route_id': route.session_id,
            'date': route.last_activity.strftime('%d.%m'),
            'city': route.city_name,
            'username': route.username,
            'points_count': route.total_points,
            'total_containers': route.total_containers,
            'status': 'completed'
        })
    
    keyboard = get_admin_route_selection_keyboard(routes_data, has_more=(len(completed_routes) > 20))
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data == "routes_summary")
async def show_routes_summary(callback: CallbackQuery) -> None:
    """Показывает общую сводку по маршрутам."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.answer("🔄 Формирую сводку...")
    
    try:
        # Получаем все данные
        all_routes = await RouteMonitor.get_active_route_sessions()
        completed_routes = await RouteMonitor.get_completed_route_sessions(days=7)
        moscow_routes = await RouteMonitor.get_moscow_routes()
        cities = await RouteMonitor.get_available_cities()
        
        # Группируем по статусам
        active_count = len([r for r in all_routes if r.status == 'active'])
        paused_count = len([r for r in all_routes if r.status == 'paused'])
        inactive_count = len([r for r in all_routes if r.status == 'inactive'])
        completed_count = len(completed_routes)
        
        # Группируем по городам (топ-5)
        city_stats = {}
        for route in all_routes + completed_routes:
            city = route.city_name
            if city not in city_stats:
                city_stats[city] = {'count': 0, 'containers': 0}
            city_stats[city]['count'] += 1
            city_stats[city]['containers'] += route.total_containers
        
        top_cities = sorted(city_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        
        # Формируем сообщение
        message_text = "📊 <b>СВОДКА ПО МАРШРУТАМ</b>\n\n"
        
        message_text += "📈 <b>По статусам:</b>\n"
        message_text += f"🟢 Активные: {active_count}\n"
        message_text += f"🟡 Приостановленные: {paused_count}\n"
        message_text += f"⚪ Неактивные: {inactive_count}\n"
        message_text += f"✅ Завершенные (7д): {completed_count}\n\n"
        
        message_text += f"🚚 <b>Маршруты в Москву:</b> {len(moscow_routes)}\n\n"
        
        message_text += "🏙️ <b>Топ городов:</b>\n"
        for i, (city, stats) in enumerate(top_cities, 1):
            message_text += f"{i}. {city}: {stats['count']} маршр., {stats['containers']} конт.\n"
        
        message_text += f"\n📍 <b>Всего городов:</b> {len(cities)}\n"
        message_text += f"📦 <b>Всего маршрутов:</b> {len(all_routes) + completed_count}"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=get_routes_monitoring_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при формировании сводки: {e}")
        await callback.answer("❌ Ошибка при формировании сводки", show_alert=True)


@admin_router.callback_query(F.data == "routes_by_cities")
async def show_cities_selection(callback: CallbackQuery) -> None:
    """Показывает выбор городов для просмотра маршрутов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    cities = await RouteMonitor.get_available_cities()
    
    if not cities:
        await callback.message.edit_text(
            "🛣️ <b>МАРШРУТЫ ПО ГОРОДАМ</b>\n\n"
            "❌ Городов с маршрутами не найдено.",
            reply_markup=get_routes_monitoring_keyboard()
        )
        return
    
    await callback.message.edit_text(
        "🛣️ <b>ВЫБЕРИТЕ ГОРОД</b>\n\n"
        "Выберите город для просмотра маршрутов:",
        reply_markup=get_city_selection_keyboard(cities)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("city_routes:"))
async def show_city_routes(callback: CallbackQuery) -> None:
    """Показывает маршруты по выбранному городу."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    city_name = callback.data.split(":", 1)[1]
    await callback.answer(f"🔄 Загружаю маршруты для {city_name}...")
    
    city_routes = await RouteMonitor.get_routes_by_city(city_name)
    
    if not city_routes:
        cities = await RouteMonitor.get_available_cities()
        await callback.message.edit_text(
            f"📍 <b>МАРШРУТЫ: {city_name.upper()}</b>\n\n"
            f"❌ Маршрутов в городе {city_name} не найдено.",
            reply_markup=get_city_selection_keyboard(cities)
        )
        return
    
    message_text = f"📍 <b>МАРШРУТЫ: {city_name.upper()}</b> ({len(city_routes)})\n\n"
    message_text += "Выберите маршрут для детального просмотра:"
    
    # Преобразуем данные в формат для клавиатуры
    routes_data = []
    for route in city_routes[:20]:  # Показываем первые 20
        routes_data.append({
            'route_id': route.session_id,
            'date': route.last_activity.strftime('%d.%m') if route.status == 'completed' else route.start_time.strftime('%d.%m'),
            'city': route.city_name,
            'username': route.username,
            'points_count': route.total_points,
            'total_containers': route.total_containers,
            'status': route.status
        })
    
    keyboard = get_admin_route_selection_keyboard(routes_data, has_more=(len(city_routes) > 20))
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data == "routes_moscow")
async def show_moscow_routes(callback: CallbackQuery) -> None:
    """Показывает маршруты в Москву."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.answer("🔄 Загружаю маршруты в Москву...")
    
    moscow_routes = await RouteMonitor.get_moscow_routes()
    
    if not moscow_routes:
        await callback.message.edit_text(
            "🚚 <b>МАРШРУТЫ В МОСКВУ</b>\n\n"
            "❌ Маршрутов в Москву не найдено.",
            reply_markup=get_routes_monitoring_keyboard()
        )
        return
    
    message_text = f"🚚 <b>МАРШРУТЫ В МОСКВУ</b> ({len(moscow_routes)})\n\n"
    message_text += "Выберите маршрут для детального просмотра:"
    
    # Преобразуем данные в формат для клавиатуры
    routes_data = []
    for route in moscow_routes[:20]:  # Показываем первые 20
        status_emoji = {
            'available': '🟢',
            'in_progress': '🟡', 
            'completed': '✅'
        }.get(route.status, '⚪')
        
        routes_data.append({
            'route_id': f"moscow_{route.route_id}",  # Префикс для различия
            'date': route.created_at.strftime('%d.%m'),
            'city': 'Москва',
            'username': route.courier_username or 'Не назначен',
            'points_count': route.points_count,
            'total_containers': route.total_containers,
            'status': route.status
        })
    
    keyboard = get_admin_route_selection_keyboard(routes_data, has_more=(len(moscow_routes) > 20))
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data == "routes_refresh")
async def refresh_routes_monitoring(callback: CallbackQuery) -> None:
    """Обновляет данные мониторинга маршрутов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.answer("🔄 Обновляю данные...")
    await callback.message.edit_text(
        "🛣️ <b>МОНИТОРИНГ МАРШРУТОВ</b>\n\n"
        "Выберите тип маршрутов для просмотра:",
        reply_markup=get_routes_monitoring_keyboard()
    )


@admin_router.callback_query(F.data == "routes_close")
async def close_routes_monitoring(callback: CallbackQuery) -> None:
    """Закрывает мониторинг маршрутов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📊 <b>СТАТИСТИКА</b>\n\n"
        "Выберите тип статистики:",
        reply_markup=get_statistics_keyboard()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "routes_monitoring_back")
async def back_to_routes_monitoring(callback: CallbackQuery) -> None:
    """Возвращает в меню мониторинга маршрутов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🛣️ <b>МОНИТОРИНГ МАРШРУТОВ</b>\n\n"
        "Выберите тип маршрутов для просмотра:",
        reply_markup=get_routes_monitoring_keyboard()
    )
    await callback.answer()


# ===============================================
# ОБРАБОТЧИКИ ДЕТАЛЬНОГО ПРОСМОТРА МАРШРУТОВ
# ===============================================

@admin_router.callback_query(F.data.startswith("admin_route:"))
async def admin_view_route_details(callback: CallbackQuery) -> None:
    """
    Обработчик выбора маршрута для детального просмотра (для админа).
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    route_hash = callback.data.split(":", 1)[1]
    
    # Получаем полный route_id по хешу
    from keyboards.admin_keyboards import get_route_id_by_hash
    session_id = get_route_id_by_hash(route_hash)
    
    # Проверяем, это маршрут в Москву или обычный маршрут
    if session_id.startswith("moscow_"):
        # Это маршрут в Москву
        moscow_route_id = int(session_id.split("_", 1)[1])
        await admin_view_moscow_route_details(callback, moscow_route_id)
        return
    
    # Обычный маршрут
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id (исключаем итоговые комментарии)
        from sqlalchemy.orm import selectinload
        from database.models import RouteProgress
        
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            and_(
                RouteProgress.route_session_id == session_id,
                RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
            )
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        # Показываем первую точку маршрута
        await admin_show_route_point_details(callback, progresses_list, 0, session_id)
    
    await callback.answer()


async def admin_view_moscow_route_details(callback: CallbackQuery, moscow_route_id: int) -> None:
    """
    Показывает детали маршрута в Москву.
    """
    async for session in get_session():
        from database.models import MoscowRoute, MoscowRoutePoint
        from sqlalchemy.orm import selectinload
        
        from database.models import User
        
        stmt = select(MoscowRoute).options(
            selectinload(MoscowRoute.route_points)
        ).where(MoscowRoute.id == moscow_route_id)
        
        moscow_route = await session.scalar(stmt)
        
        if not moscow_route:
            await callback.answer("❌ Маршрут в Москву не найден", show_alert=True)
            return
        
        # Получаем имя курьера
        courier_name = "Не назначен"
        if moscow_route.courier_id:
            courier = await session.scalar(
                select(User).where(User.telegram_id == moscow_route.courier_id)
            )
            if courier:
                courier_name = courier.username or f"User_{courier.telegram_id}"
        
        # Формируем сообщение с деталями маршрута
        message_text = f"🚚 <b>МАРШРУТ В МОСКВУ #{moscow_route.id}</b>\n\n"
        
        message_text += f"📋 <b>Название:</b> {moscow_route.route_name}\n"
        message_text += f"👤 <b>Курьер:</b> {courier_name}\n"
        message_text += f"📊 <b>Статус:</b> {moscow_route.status}\n"
        message_text += f"📍 <b>Точек:</b> {len(moscow_route.route_points)}\n"
        message_text += f"🕐 <b>Создан:</b> {moscow_route.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if moscow_route.started_at:
            message_text += f"🚀 <b>Начат:</b> {moscow_route.started_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if moscow_route.completed_at:
            message_text += f"✅ <b>Завершен:</b> {moscow_route.completed_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        message_text += f"\n📦 <b>Точки доставки:</b>\n"
        
        total_containers = 0
        for i, point in enumerate(moscow_route.route_points, 1):
            total_containers += point.containers_to_deliver
            delivered_containers = point.containers_delivered or 0
            
            status_emoji = "✅" if point.status == 'completed' else "⏳"
            message_text += (
                f"\n{status_emoji} <b>{i}. {point.organization}</b>\n"
                f"📍 {point.point_name}\n"
                f"📦 {delivered_containers}/{point.containers_to_deliver} контейнеров\n"
            )
        
        message_text += f"\n📦 <b>Всего контейнеров:</b> {total_containers}"
        
        # Создаем клавиатуру возврата
        from keyboards.admin_keyboards import get_routes_monitoring_keyboard
        keyboard = get_routes_monitoring_keyboard()
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard
        )


async def admin_show_route_point_details(
    callback: CallbackQuery, 
    progresses_list: list, 
    point_index: int, 
    route_id: str
) -> None:
    """
    Показывает детали конкретной точки маршрута (для админа).
    """
    if point_index >= len(progresses_list):
        await callback.answer("❌ Точка не найдена", show_alert=True)
        return
    
    progress = progresses_list[point_index]
    route = progress.route
    photos = progress.photos
    
    # Формируем сообщение с деталями точки
    message_text = f"📍 <b>ТОЧКА {point_index + 1} из {len(progresses_list)}</b>\n\n"
    
    message_text += f"🏢 <b>{route.organization}</b>\n"
    message_text += f"📍 {route.point_name}\n"
    message_text += f"🏙️ {route.city_name}\n"
    message_text += f"📍 {route.address}\n\n"
    
    message_text += f"📦 <b>Контейнеров:</b> {progress.containers_count}\n"
    message_text += f"📅 <b>Время:</b> {progress.visited_at.strftime('%d.%m.%Y %H:%M')}\n"
    message_text += f"📸 <b>Фотографий:</b> {len(photos)}\n"
    message_text += f"✅ <b>Статус:</b> {progress.status}\n\n"
    
    if progress.notes:
        message_text += f"💬 <b>Комментарий:</b>\n{progress.notes}\n\n"
    
    message_text += f"🆔 <b>Сессия:</b> <code>{route_id}</code>"
    
    # Проверяем есть ли лабораторные данные
    has_lab_data = any("ЛАБОРАТОРНЫЕ_ДАННЫЕ" in p.notes or "ИТОГОВЫЙ_КОММЕНТАРИЙ" in p.notes 
                      for p in progresses_list if p.notes)
    
    keyboard = get_admin_route_detail_keyboard(
        route_id=route_id,
        current_point_index=point_index,
        total_points=len(progresses_list),
        has_photos=len(photos) > 0,
        has_lab_data=has_lab_data
    )
    
    try:
        # Проверяем, содержит ли сообщение фото
        if callback.message.photo:
            # Если это сообщение с фото, отправляем новое текстовое сообщение
            await callback.message.answer(
                text=message_text,
                reply_markup=keyboard
            )
            # Удаляем старое сообщение с фото
            try:
                await callback.message.delete()
            except:
                pass  # Игнорируем ошибку удаления
        else:
            # Если это текстовое сообщение, редактируем его
            await callback.message.edit_text(
                text=message_text,
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении сообщения: {e}")
        logger.error(f"Route ID: {route_id}, Point index: {point_index}, Total points: {len(progresses_list)}")
        # Fallback: отправляем новое сообщение
        try:
            await callback.message.answer(
                text=message_text,
                reply_markup=keyboard
            )
            await callback.answer("⚠️ Отправлено новое сообщение")
        except Exception as fallback_error:
            logger.error(f"Fallback тоже не сработал: {fallback_error}")
            await callback.answer("❌ Ошибка при загрузке деталей точки")


@admin_router.callback_query(F.data.startswith("admin_route_point:"))
async def admin_navigate_route_point(callback: CallbackQuery) -> None:
    """
    Обработчик навигации по точкам маршрута (для админа).
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка в данных", show_alert=True)
        return
    
    route_hash = parts[1]
    point_index = int(parts[2])
    
    # Получаем полный route_id по хешу
    from keyboards.admin_keyboards import get_route_id_by_hash
    session_id = get_route_id_by_hash(route_hash)
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id
        from sqlalchemy.orm import selectinload
        from database.models import RouteProgress
        
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            and_(
                RouteProgress.route_session_id == session_id,
                RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
            )
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        # Показываем выбранную точку
        await admin_show_route_point_details(callback, progresses_list, point_index, session_id)
    
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_view_photos:"))
async def admin_view_route_photos(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра фотографий точки маршрута (для админа).
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка в данных", show_alert=True)
        return
    
    route_hash = parts[1]
    point_index = int(parts[2])
    
    # Получаем полный route_id по хешу
    from keyboards.admin_keyboards import get_route_id_by_hash
    session_id = get_route_id_by_hash(route_hash)
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id (исключаем итоговые комментарии)
        from sqlalchemy.orm import selectinload
        from database.models import RouteProgress
        
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            and_(
                RouteProgress.route_session_id == session_id,
                RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
            )
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        if point_index >= len(progresses_list):
            await callback.answer("❌ Точка не найдена", show_alert=True)
            return
        
        progress = progresses_list[point_index]
        photos = progress.photos
        
        if not photos:
            await callback.answer("❌ Фотографий нет", show_alert=True)
            return
        
        # Показываем первую фотографию
        await admin_show_route_photo(callback, photos, 0, session_id, point_index)
    
    await callback.answer()


async def admin_show_route_photo(
    callback: CallbackQuery, 
    photos: list, 
    photo_index: int, 
    route_id: str, 
    point_index: int
) -> None:
    """
    Показывает фотографию точки маршрута (для админа).
    """
    if photo_index >= len(photos):
        await callback.answer("❌ Фотография не найдена", show_alert=True)
        return
    
    photo = photos[photo_index]
    
    caption = (
        f"📸 <b>Фото {photo_index + 1} из {len(photos)}</b>\n\n"
        f"📅 {photo.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🆔 Сессия: `{route_id}`"
    )
    
    keyboard = get_admin_photos_viewer_keyboard(
        route_id=route_id,
        point_index=point_index,
        current_photo_index=photo_index,
        total_photos=len(photos)
    )
    
    try:
        # Если текущее сообщение содержит фото, редактируем медиа
        if callback.message.photo:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=photo.file_id,
                    caption=caption
                ),
                reply_markup=keyboard
            )
        else:
            # Если это текстовое сообщение, отправляем новое с фото
            await callback.message.answer_photo(
                photo=photo.file_id,
                caption=caption,
                reply_markup=keyboard
            )
            # Удаляем старое текстовое сообщение
            try:
                await callback.message.delete()
            except:
                pass  # Игнорируем ошибку удаления
    except Exception as e:
        logger.error(f"Ошибка при показе фото: {e}")
        await callback.answer("❌ Ошибка при загрузке фотографии")


@admin_router.callback_query(F.data.startswith("admin_photo:"))
async def admin_navigate_route_photo(callback: CallbackQuery) -> None:
    """
    Обработчик навигации по фотографиям точки маршрута (для админа).
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Ошибка в данных", show_alert=True)
        return
    
    route_hash = parts[1]
    point_index = int(parts[2])
    photo_index = int(parts[3])
    
    # Получаем полный route_id по хешу
    from keyboards.admin_keyboards import get_route_id_by_hash
    session_id = get_route_id_by_hash(route_hash)
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id (исключаем итоговые комментарии)
        from sqlalchemy.orm import selectinload
        from database.models import RouteProgress
        
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.photos)
        ).where(
            and_(
                RouteProgress.route_session_id == session_id,
                RouteProgress.notes.notlike('%ИТОГОВЫЙ_КОММЕНТАРИЙ%'),
                RouteProgress.notes.notlike('%ЛАБОРАТОРНЫЕ_ДАННЫЕ%')
            )
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        if point_index >= len(progresses_list):
            await callback.answer("❌ Точка не найдена", show_alert=True)
            return
        
        progress = progresses_list[point_index]
        photos = progress.photos
        
        if not photos:
            await callback.answer("❌ Фотографий нет", show_alert=True)
            return
        
        # Показываем выбранную фотографию
        await admin_show_route_photo(callback, photos, photo_index, session_id, point_index)
    
    await callback.answer()


@admin_router.callback_query(F.data == "admin_back_to_routes")
async def admin_back_to_routes(callback: CallbackQuery) -> None:
    """Возвращает к списку маршрутов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    # Возвращаемся в главное меню мониторинга
    await callback.message.edit_text(
        "🛣️ <b>МОНИТОРИНГ МАРШРУТОВ</b>\n\n"
        "Выберите тип маршрутов для просмотра:",
        reply_markup=get_routes_monitoring_keyboard()
    )
    await callback.answer()