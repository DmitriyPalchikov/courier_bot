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
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from database.database import get_session
from database.models import User, Route, RouteProgress, Delivery
from keyboards.admin_keyboards import (
    get_admin_menu_keyboard,
    get_statistics_keyboard,
    get_export_keyboard,
    get_settings_keyboard,
    get_period_selection_keyboard
)
from utils.statistics import (
    get_route_statistics,
    get_user_performance,
    get_busiest_days,
    format_statistics_message
)
from utils.report_generator import generate_excel_report, generate_pdf_report
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