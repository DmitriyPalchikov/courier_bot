"""
Обработчики сообщений и действий пользователей курьерского бота.

Этот модуль содержит все функции для обработки пользовательских команд,
сообщений и взаимодействий. Каждый обработчик отвечает за определённый
тип действий пользователя.

Основные группы обработчиков:
- Команды бота (/start, /help)
- Выбор и прохождение маршрутов
- Загрузка фотографий и подсчёт контейнеров
- Завершение маршрутов
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PhotoSize, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from utils.progress_bar import format_route_progress, format_route_summary

# Импорты наших модулей
from database.database import get_session
from database.models import User, Route, RouteProgress, Delivery, RoutePhoto, LabSummary, LabSummaryPhoto, MoscowRoute
from utils.callback_manager import (
    parse_callback,
    create_lab_data_callback, create_specific_lab_callback, create_lab_photo_callback,
    create_lab_comment_callback, create_back_to_route_callback
)
from states.user_states import RouteStates
from keyboards.user_keyboards import (
    get_main_menu_keyboard,
    get_cities_keyboard, 
    get_route_points_keyboard,
    get_confirmation_keyboard,
    get_complete_route_keyboard,
    get_photo_actions_keyboard,
    get_finish_photos_keyboard,
    get_point_data_management_keyboard,
    get_route_selection_keyboard,
    get_route_detail_keyboard,
    get_photos_viewer_keyboard,
    get_lab_selection_keyboard,
    get_lab_summary_management_keyboard,
    get_lab_photos_keyboard,
    get_lab_comment_confirmation_keyboard,
    get_route_lab_data_keyboard,
    get_lab_data_viewer_keyboard,
    get_point_action_keyboard,
    get_moscow_final_comment_keyboard
)
from config import (
    WELCOME_MESSAGE,
    HELP_MESSAGE, 
    ERROR_MESSAGES,
    AVAILABLE_ROUTES,
    MOSCOW_DELIVERY_ADDRESSES,
    MIN_CONTAINERS,
    MAX_CONTAINERS
)
from utils.route_manager import RouteManager

# Создаём роутер для пользовательских обработчиков
user_router = Router(name='user_router')

# Настраиваем логирование
logger = logging.getLogger(__name__)


@user_router.message(Command('start'))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    
    Эта функция:
    1. Регистрирует нового пользователя в базе данных
    2. Отправляет приветственное сообщение
    3. Показывает главное меню
    4. Очищает состояние FSM если оно было установлено
    
    Args:
        message: Объект сообщения от пользователя
        state: Контекст состояния FSM для данного пользователя
    """
    # Очищаем любые предыдущие состояния
    await state.clear()
    
    # Получаем информацию о пользователе из Telegram
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Работаем с базой данных
    async for session in get_session():
        # Проверяем, существует ли пользователь в базе
        result = await session.get(User, user_id)
        
        if not result:
            # Создаём нового пользователя
            new_user = User(
                telegram_id=user_id,
                username=username,
                full_name=full_name,
                is_active=True
            )
            session.add(new_user)
            await session.commit()
            
            logger.info(f"Зарегистрирован новый пользователь: {user_id} (@{username})")
        else:
            # Обновляем информацию существующего пользователя
            result.username = username
            result.full_name = full_name
            result.is_active = True
            await session.commit()
            
            logger.info(f"Пользователь {user_id} снова активен")
    
    # Отправляем приветственное сообщение с главным меню
    await message.answer(
        text=WELCOME_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )


@user_router.message(Command('help'))
async def cmd_help(message: Message) -> None:
    """
    Обработчик команды /help.
    
    Отправляет пользователю подробную инструкцию по использованию бота.
    
    Args:
        message: Объект сообщения от пользователя
    """
    await message.answer(
        text=HELP_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )


@user_router.message(F.text == "❓ Помощь")
async def help_button(message: Message) -> None:
    """
    Обработчик кнопки "❓ Помощь".
    
    Отправляет пользователю подробную инструкцию по использованию бота.
    
    Args:
        message: Объект сообщения от пользователя
    """
    await message.answer(
        text=HELP_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )


@user_router.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message) -> None:
    """
    Обработчик кнопки "ℹ️ О боте".
    
    Отправляет пользователю информацию о боте и его возможностях.
    
    Args:
        message: Объект сообщения от пользователя
    """
    about_text = """
ℹ️ <b>О боте курьерской службы</b>

🤖 <b>Назначение:</b>
Этот бот помогает курьерам эффективно выполнять маршруты по сбору контейнеров с медицинскими образцами из различных лабораторий.

🎯 <b>Основные функции:</b>
• 📋 Ведение маршрутов по городам
• 📸 Фиксация процесса сбора фотографиями
• 📦 Учет количества собранных контейнеров
• 💬 Возможность оставлять комментарии
• 🏥 Отчеты по лабораториям
• 📊 История выполненных маршрутов

🏢 <b>Поддерживаемые организации:</b>
• КДЛ (Клинико-диагностические лаборатории)
• Ховер (медицинские центры)
• Дартис (диагностические центры)

📱 <b>Как пользоваться:</b>
Нажмите "❓ Помощь" для получения подробной инструкции

👨‍💻 <b>Разработчик:</b> Пальчиков Дмитрий Андреевич
📅 <b>Версия:</b> Сентябрь 2025

Удачной работы! 🚚✨
"""
    await message.answer(
        text=about_text,
        reply_markup=get_main_menu_keyboard()
    )


@user_router.message(F.text == "🚚 Выбрать маршрут")
async def select_route(message: Message, state: FSMContext) -> None:
    """
    Начало выбора маршрута.
    
    Показывает пользователю доступные города для маршрутов
    и переводит в состояние ожидания выбора города.
    
    Args:
        message: Объект сообщения от пользователя
        state: Контекст состояния FSM
    """
    # Проверяем, нет ли активного маршрута у пользователя
    async for session in get_session():
        # Получаем незавершённый маршрут пользователя
        stmt = select(RouteProgress).where(
            and_(
                RouteProgress.user_id == message.from_user.id,
                RouteProgress.status.in_(['pending', 'in_progress'])
            )
        )
        active_route = await session.scalar(stmt)
        
        if active_route:
            await message.answer(
                "❗️ У вас уже есть активный маршрут. Завершите его перед началом нового.",
                reply_markup=get_main_menu_keyboard()
            )
            return
    
    # Устанавливаем состояние ожидания выбора города
    await state.set_state(RouteStates.waiting_for_city_selection)
    
    # Используем асинхронную функцию для получения городов
    from keyboards.user_keyboards import get_cities_keyboard_async
    cities_keyboard = await get_cities_keyboard_async()
    
    await message.answer(
        "🏙️ Выберите город для маршрута:",
        reply_markup=cities_keyboard
    )


@user_router.callback_query(F.data.startswith("city:"), RouteStates.waiting_for_city_selection)
async def city_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора города для маршрута.
    
    Показывает информацию о маршруте и запрашивает подтверждение.
    """
    # Приводим callback.data к строке
    raw_data = callback.data
    if isinstance(raw_data, (list, tuple)):
        raw_data = raw_data[0]
    city_name = str(raw_data).split(":", 1)[1]
    
    # Получаем все доступные маршруты (включая динамические в Москву)
    from utils.route_selector import RouteSelector
    all_routes = await RouteSelector.get_all_available_routes()
    
    # Проверяем, что город существует
    if city_name not in all_routes:
        await callback.answer("❌ Неизвестный город", show_alert=True)
        return
    
    # Получаем точки маршрута для выбранного города
    route_points = all_routes[city_name]
    
    # Получаем информацию о типе маршрута
    route_info_data = await RouteSelector.get_route_info(city_name, route_points)
    
    # Для маршрутов в Москву получаем moscow_route_id
    moscow_route_id = None
    if route_info_data['action_type'] == 'delivery' and route_points:
        moscow_route_id = route_points[0].get('moscow_route_id')
    
    # Сохраняем выбранный город и маршрут
    await state.update_data(
        selected_city=city_name,
        route_points=route_points,
        current_point_index=0,
        collected_containers={},
        completed_points=0,  # Добавляем счетчик завершенных точек
        route_type=route_info_data['action_type'],  # Тип маршрута: collection или delivery
        moscow_route_id=moscow_route_id  # ID маршрута в Москву (если применимо)
    )
    
    # Переводим в состояние ожидания подтверждения
    await state.set_state(RouteStates.waiting_for_route_confirmation)
    
    # Формируем информацию о маршруте
    if route_info_data['action_type'] == 'delivery':
        # Маршрут доставки в Москву
        route_info = f"🚚 <b>Маршрут доставки: {route_info_data['route_name']}</b>\n\n"
        route_info += f"📦 <b>Контейнеров к доставке:</b> {route_info_data['total_containers']}\n"
        route_info += f"📋 <b>Точек доставки ({len(route_points)}):</b>\n\n"
        
        for i, point in enumerate(route_points, 1):
            containers = point.get('containers_to_deliver', 0)
            route_info += f"{i}. <b>{point['organization']}</b>\n"
            route_info += f"   📦 Доставить: {containers} контейнеров\n"
            route_info += f"   📍 {point['address']}\n\n"
        
        route_info += "🔄 <b>Тип маршрута:</b> Доставка (отдача контейнеров)\n\n"
    else:
        # Маршрут сбора
        route_info = f"📦 <b>Выбранный маршрут: {city_name}</b>\n\n"
        route_info += f"📋 <b>Точки для посещения ({len(route_points)}):</b>\n\n"
        
        for i, point in enumerate(route_points, 1):
            route_info += f"{i}. <b>{point['organization']}</b> - {point['name']}\n"
            route_info += f"   📍 {point['address']}\n\n"
        
        route_info += "🔄 <b>Тип маршрута:</b> Сбор (получение контейнеров)\n\n"
    
    route_info += "❓ <b>Подтвердите выбор маршрута:</b>"
    
    # Создаём клавиатуру подтверждения
    from keyboards.user_keyboards import get_confirmation_keyboard
    
    await callback.message.edit_text(
        text=route_info,
        reply_markup=get_confirmation_keyboard(
            confirm_text="✅ Начать маршрут",
            cancel_text="❌ Выбрать другой город",
            confirm_callback="confirm_route_start",
            cancel_callback="back_to_city_selection"
        )
    )
    
    await callback.answer()

@user_router.callback_query(F.data == "confirm_route_start", RouteStates.waiting_for_route_confirmation)
async def confirm_route_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Подтверждение начала маршрута.
    
    Переходит к первой точке маршрута.
    """
    state_data = await state.get_data()
    selected_city = state_data.get('selected_city')
    route_points = state_data.get('route_points')
    
    if not route_points:
        await callback.answer("❌ Ошибка: маршрут не найден", show_alert=True)
        await state.clear()
        return
    
    # Генерируем уникальный ID сессии маршрута
    from utils.route_session import generate_route_session_id
    route_session_id = generate_route_session_id(callback.from_user.id, selected_city)
    
    # Начинаем с первой точки маршрута
    current_point = route_points[0]
    
    # Обновляем данные состояния
    await state.update_data(
        current_point=current_point,
        total_points=len(route_points),
        route_session_id=route_session_id
    )
    
    # Переводим в состояние ожидания фотографии
    await state.set_state(RouteStates.waiting_for_photo)
    
    # Сохраняем время начала маршрута
    await state.update_data(route_start_time=datetime.now().isoformat())
    
    # Формируем сообщение о первой точке с прогресс-баром
    point_info = format_route_progress(
        city=selected_city,
        current_point=current_point,
        total_points=len(route_points),
        current_index=0,
        collected_containers={},
        completed_points=0  # На первой точке еще ничего не завершено
    )
    point_info += "\n\n🎯 Выберите действие с данной точкой:"
    
    await callback.message.edit_text(
        text=point_info,
        reply_markup=get_point_action_keyboard()
    )
    
    await callback.answer("Маршрут начат!")


@user_router.callback_query(F.data == "back_to_city_selection", RouteStates.waiting_for_route_confirmation)
async def back_to_city_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Возврат к выбору города.
    
    Отменяет текущий выбор и показывает список городов снова.
    """
    # Возвращаемся к состоянию выбора города
    await state.set_state(RouteStates.waiting_for_city_selection)
    
    # Очищаем данные выбранного маршрута
    await state.update_data(
        selected_city=None,
        route_points=None,
        current_point=None
    )
    
    await callback.message.edit_text(
        text="🏙️ Выберите город для маршрута:",
        reply_markup=get_cities_keyboard()
    )
    
    await callback.answer("Выбор отменён")


@user_router.callback_query(F.data == "cancel_city_selection")
async def cancel_city_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик отмены выбора города.
    
    Очищает состояние FSM и возвращает пользователя в главное меню.
    
    Args:
        callback: Объект callback query от кнопки отмены
        state: Контекст состояния FSM
    """
    # Очищаем все состояния FSM
    await state.clear()
    
    # Редактируем сообщение БЕЗ клавиатуры
    await callback.message.edit_text(
        text="❌ Выбор маршрута отменён.",
        reply_markup=None
    )
    
    # Отправляем новое сообщение с Reply-клавиатурой
    await callback.message.answer(
        text="Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer("Выбор маршрута отменён")



@user_router.callback_query(F.data == "cancel_route")
async def cancel_route(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик отмены активного маршрута.
    
    Показывает подтверждение отмены маршрута.
    
    Args:
        callback: Объект callback query от кнопки отмены маршрута
        state: Контекст состояния FSM
    """
    await callback.message.edit_text(
        text="⚠️ <b>Вы действительно хотите отменить текущий маршрут?</b>\n\n"
             "Весь прогресс будет потерян!",
        reply_markup=get_confirmation_keyboard(
            confirm_text="✅ Да, отменить",
            cancel_text="❌ Продолжить маршрут", 
            confirm_callback="confirm_cancel_route",
            cancel_callback="back_to_route"
        )
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "confirm_cancel_route")
async def confirm_cancel_route(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Подтверждение отмены маршрута.
    """
    # Очищаем состояние
    await state.clear()
    
    await callback.message.edit_text(
        text="✅ Маршрут отменён.",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer("Маршрут отменён")

@user_router.callback_query(F.data == "back_to_route")
async def back_to_route(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Возврат к активному маршруту.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    
    if current_point:
        point_info = (
            f"📍 <b>Текущая точка маршрута:</b>\n\n"
            f"🏢 <b>Организация:</b> {current_point['organization']}\n"
            f"🏠 <b>Адрес:</b> {current_point['address']}\n\n"
            f"🎯 Выберите действие с данной точкой:"
        )
        
        await callback.message.edit_text(
            text=point_info,
            reply_markup=get_point_action_keyboard()
        )
    else:
        await callback.message.edit_text(
            text="❌ Активный маршрут не найден",
            reply_markup=None
        )
        
        await callback.message.answer(
            text="🏠 Главное меню:",
            reply_markup=get_main_menu_keyboard()
        )
    
    await callback.answer()

@user_router.message(F.photo, RouteStates.waiting_for_photo)
async def photo_received(message: Message, state: FSMContext) -> None:
    """
    Обработчик получения фотографии с точки маршрута.
    
    Сохраняет фотографию и переводит в состояние ожидания
    количества собранных контейнеров.
    
    Args:
        message: Объект сообщения с фотографией
        state: Контекст состояния FSM
    """
    # Получаем данные текущего состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    
    if not current_point:
        await message.answer(ERROR_MESSAGES['route_not_selected'])
        await state.clear()
        return
    
    # Сохраняем file_id фотографии (самого большого размера)
    photo: PhotoSize = message.photo[-1]
    
    # Инициализируем список фотографий в состоянии
    photos_list = state_data.get('photos_list', [])
    photos_list.append(photo.file_id)
    
    await state.update_data(photos_list=photos_list)
    
    # Переводим в новое состояние управления данными точки
    await state.set_state(RouteStates.managing_point_data)
    
    await message.answer(
        f"📸 Фотография получена! ({len(photos_list)} шт.)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Теперь заполните данные для точки:",
        reply_markup=get_point_data_management_keyboard(
            has_photos=True,
            has_containers=False,
            has_comment=False,
            photos_count=len(photos_list),
            containers_count=None,
            comment_text=""
        )
    )


@user_router.callback_query(F.data == "add_more_photos", RouteStates.waiting_for_photo_decision)
async def add_more_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки "Добавить еще фото".
    
    Переводит пользователя в состояние ожидания дополнительных фотографий.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    
    # Переводим в состояние ожидания дополнительных фотографий
    await state.set_state(RouteStates.waiting_for_additional_photos)
    
    await callback.message.edit_text(
        f"📸 Добавляем фотографии ({len(photos_list)} уже добавлено)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"📷 Отправьте следующую фотографию или нажмите 'Готово'",
        reply_markup=get_finish_photos_keyboard(len(photos_list))
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "proceed_to_boxes", RouteStates.waiting_for_photo_decision)
async def proceed_to_boxes(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки "Указать количество контейнеров".
    
    Переводит пользователя к вводу количества контейнеров.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    route_type = state_data.get('route_type', 'collection')
    
    # Переводим в состояние ожидания количества контейнеров
    await state.set_state(RouteStates.waiting_for_containers_count)
    
    # Формируем сообщение в зависимости от типа маршрута
    if route_type == 'delivery':
        containers_to_deliver = current_point.get('containers_to_deliver', 0)
        point_name = current_point.get('point_name', current_point.get('name', 'Неизвестная точка'))
        message_text = (
            f"📦 Фотографии сохранены!\n\n"
            f"📍 Точка доставки: <b>{point_name}</b>\n"
            f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
            f"🚚 <b>У вас с собой:</b> {containers_to_deliver} контейнеров\n\n"
            f"Укажите количество контейнеров, которые необходимо отгрузить:\n"
            f"Введите число от {MIN_CONTAINERS} до {containers_to_deliver}:"
        )
    else:
        message_text = (
            f"📦 Фотографии сохранены!\n\n"
            f"📍 Точка: <b>{current_point['name']}</b>\n"
            f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
            f"Укажите количество собранных контейнеров\n"
            f"Введите число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
        )
    
    await callback.message.edit_text(message_text)
    await callback.answer()


@user_router.message(F.photo, RouteStates.waiting_for_additional_photos)
async def additional_photo_received(message: Message, state: FSMContext) -> None:
    """
    Обработчик получения дополнительных фотографий.
    """
    # Получаем данные состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    
    # Сохраняем новую фотографию
    photo: PhotoSize = message.photo[-1]
    photos_list.append(photo.file_id)
    
    await state.update_data(photos_list=photos_list)
    
    await message.answer(
        f"📸 Фотография добавлена! ({len(photos_list)} всего)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Продолжайте добавлять фото или завершите добавление",
        reply_markup=get_finish_photos_keyboard(len(photos_list))
    )


@user_router.callback_query(F.data == "add_one_more_photo", RouteStates.waiting_for_additional_photos)
async def add_one_more_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки "Добавить еще" в режиме дополнительных фотографий.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    
    await callback.message.edit_text(
        f"📸 Добавляем фотографии ({len(photos_list)} уже добавлено)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"📷 Отправьте следующую фотографию"
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "finish_photos", RouteStates.waiting_for_additional_photos)
async def finish_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки "Готово" - завершение добавления фотографий.
    Возвращает в состояние управления данными точки.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    containers_count = state_data.get('containers_count', None)
    comment = state_data.get('comment', '')
    
    # Переводим в состояние управления данными точки
    await state.set_state(RouteStates.managing_point_data)
    
    status_text = _get_point_status_text(state_data, current_point)
    
    await callback.message.edit_text(
        status_text,
        reply_markup=get_point_data_management_keyboard(
            has_photos=len(photos_list) > 0,
            has_containers=containers_count is not None,
            has_comment=bool(comment),
            photos_count=len(photos_list),
            containers_count=containers_count,
            comment_text=comment
        )
    )
    
    await callback.answer()


@user_router.message(F.text, RouteStates.waiting_for_containers_count)
async def containers_count_received(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Обработчик получения количества контейнеров.
    
    Проверяет корректность введённого числа, сохраняет прогресс
    в базу данных и переходит к следующей точке или завершению маршрута.
    
    Args:
        message: Объект сообщения с количеством контейнеров
        state: Контекст состояния FSM
        bot: Объект бота для отправки сообщений
    """
    # Проверяем, что введено число
    try:
        containers_count = int(message.text.strip())
    except ValueError:
        # Сохраняем состояние для повторного ввода
        await state.set_state(RouteStates.waiting_for_containers_count)
        await message.answer(
            f"❌ Ошибка: введите число (не текст)\n\n"
            f"📦 Количество контейнеров должно быть от {MIN_CONTAINERS} до {MAX_CONTAINERS}\n"
            f"Попробуйте еще раз:"
        )
        return
    
    # Проверяем диапазон
    if containers_count < MIN_CONTAINERS or containers_count > MAX_CONTAINERS:
        # Сохраняем состояние для повторного ввода
        await state.set_state(RouteStates.waiting_for_containers_count)
        await message.answer(
            f"❌ Неверный диапазон!\n\n"
            f"📦 Количество контейнеров должно быть от {MIN_CONTAINERS} до {MAX_CONTAINERS}\n"
            f"Вы ввели: {containers_count}\n\n"
            f"Попробуйте еще раз:"
        )
        return
    
    # Получаем данные состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    selected_city = state_data.get('selected_city')
    current_point_index = state_data.get('current_point_index', 0)
    total_points = state_data.get('total_points', 0)
    collected_containers = state_data.get('collected_containers', {})
    route_type = state_data.get('route_type', 'collection')  # collection или delivery
    
    # Для маршрутов доставки проверяем, что не превышаем количество контейнеров с собой
    if route_type == 'delivery':
        containers_to_deliver = current_point.get('containers_to_deliver', 0)
        if containers_count > containers_to_deliver:
            await state.set_state(RouteStates.waiting_for_containers_count)
            await message.answer(
                f"❌ Ошибка: у вас с собой только {containers_to_deliver} контейнеров для {current_point['organization']}\n\n"
                f"Вы можете отдать максимум {containers_to_deliver} контейнеров\n"
                f"Вы ввели: {containers_count}\n\n"
                f"Попробуйте еще раз:"
            )
            return
    
    # Сохраняем количество контейнеров в состоянии и возвращаемся к управлению данными
    await state.update_data(containers_count=containers_count)
    await state.set_state(RouteStates.managing_point_data)
    
    # Получаем обновленные данные для отображения статуса
    state_data = await state.get_data()
    photos_list = state_data.get('photos_list', [])
    comment = state_data.get('comment', '')
    
    status_text = _get_point_status_text(state_data, current_point)
    
    # Формируем сообщение в зависимости от типа маршрута
    if route_type == 'delivery':
        success_message = f"✅ Количество отданных контейнеров: {containers_count}\n\n"
    else:
        success_message = f"✅ Количество собранных контейнеров: {containers_count}\n\n"
    
    await message.answer(
        success_message + status_text,
        reply_markup=get_point_data_management_keyboard(
            has_photos=len(photos_list) > 0,
            has_containers=True,
            has_comment=bool(comment),
            photos_count=len(photos_list),
            containers_count=containers_count,
            comment_text=comment
        )
    )


@user_router.message(F.text, RouteStates.waiting_for_comment)
async def comment_received(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Обработчик получения комментария к точке маршрута.
    
    Сохраняет комментарий и возвращает в состояние управления данными точки.
    
    Args:
        message: Объект сообщения с комментарием
        state: Контекст состояния FSM  
        bot: Объект бота для отправки сообщений
    """
    comment = message.text.strip()
    
    # Проверяем длину комментария
    if len(comment) > 500:
        # Сохраняем состояние для повторного ввода
        await state.set_state(RouteStates.waiting_for_comment)
        await message.answer(
            f"❌ Комментарий слишком длинный!\n\n"
            f"📝 Максимальная длина: 500 символов\n"
            f"У вас: {len(comment)} символов\n\n"
            f"Сократите текст и попробуйте еще раз:"
        )
        return
    
    # Получаем данные состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    containers_count = state_data.get('containers_count', None)
    
    # Сохраняем комментарий в состоянии
    await state.update_data(comment=comment)
    await state.set_state(RouteStates.managing_point_data)
    
    # Получаем обновленные данные для отображения статуса
    state_data = await state.get_data()
    
    status_text = _get_point_status_text(state_data, current_point)
    
    await message.answer(
        f"✅ Комментарий сохранен!\n\n" + status_text,
        reply_markup=get_point_data_management_keyboard(
            has_photos=len(photos_list) > 0,
            has_containers=containers_count is not None,
            has_comment=True,
            photos_count=len(photos_list),
            containers_count=containers_count,
            comment_text=comment
        )
    )


# ==============================================
# НОВЫЕ ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ ДАННЫМИ ТОЧКИ
# ==============================================

def _get_point_status_text(state_data: dict, current_point: dict) -> str:
    """
    Формирует текст со статусом заполнения данных точки.
    """
    photos_list = state_data.get('photos_list', [])
    containers_count = state_data.get('containers_count', None)
    comment = state_data.get('comment', '')
    route_type = state_data.get('route_type', 'collection')
    
    # Название точки зависит от типа маршрута
    if route_type == 'delivery':
        point_name = current_point.get('point_name', current_point.get('name', 'Неизвестная точка'))
        containers_to_deliver = current_point.get('containers_to_deliver', 0)
        status_text = f"📍 Точка доставки: <b>{point_name}</b>\n"
        status_text += f"🏢 Организация: <b>{current_point['organization']}</b>\n"
        status_text += f"📦 К доставке: {containers_to_deliver} контейнеров\n\n"
    else:
        status_text = f"📍 Точка сбора: <b>{current_point['name']}</b>\n"
        status_text += f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
    
    status_text += "📊 Статус заполнения:\n"
    status_text += f"📸 Фото: {'✅' if photos_list else '❌'} ({len(photos_list)} шт.)\n"
    
    if route_type == 'delivery':
        status_text += f"📦 Отдано: {'✅' if containers_count is not None else '❌'} ({containers_count if containers_count is not None else '—'} шт.)\n"
    else:
        status_text += f"📦 Собрано: {'✅' if containers_count is not None else '❌'} ({containers_count if containers_count is not None else '—'} шт.)\n"
    
    status_text += f"📝 Комментарий: {'✅' if comment else '❌'}\n\n"
    
    if photos_list and containers_count is not None and comment:
        if route_type == 'delivery':
            status_text += "🚀 Все данные заполнены! Можете продолжить доставку."
        else:
            status_text += "🚀 Все данные заполнены! Можете продолжить маршрут."
    else:
        status_text += "⚠️ Заполните все необходимые данные для продолжения."
    
    return status_text


@user_router.callback_query(F.data == "add_photos", RouteStates.managing_point_data)
async def add_photos_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки добавления фотографий из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_additional_photos)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    
    await callback.message.edit_text(
        f"📸 Добавляем фотографии ({len(photos_list)} уже добавлено)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"📷 Отправьте фотографию или нажмите 'Готово'",
        reply_markup=get_finish_photos_keyboard(len(photos_list))
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "edit_photos", RouteStates.managing_point_data)
async def edit_photos_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки редактирования фотографий из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_additional_photos)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    
    await callback.message.edit_text(
        f"📸 Редактируем фотографии ({len(photos_list)} шт.)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"📷 Отправьте новую фотографию или нажмите 'Готово' для возврата",
        reply_markup=get_finish_photos_keyboard(len(photos_list))
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "add_containers", RouteStates.managing_point_data)
async def add_containers_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки добавления контейнеров из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_containers_count)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    route_type = state_data.get('route_type', 'collection')
    
    # Формируем сообщение в зависимости от типа маршрута
    if route_type == 'delivery':
        containers_to_deliver = current_point.get('containers_to_deliver', 0)
        point_name = current_point.get('point_name', current_point.get('name', 'Неизвестная точка'))
        message_text = (
            f"📦 Укажите количество контейнеров для отгрузки\n\n"
            f"📍 Точка доставки: <b>{point_name}</b>\n"
            f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
            f"🚚 <b>У вас с собой:</b> {containers_to_deliver} контейнеров\n\n"
            f"Введите число от {MIN_CONTAINERS} до {containers_to_deliver}:"
        )
    else:
        message_text = (
            f"📦 Укажите количество собранных контейнеров\n\n"
            f"📍 Точка: <b>{current_point['name']}</b>\n"
            f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
            f"Введите число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
        )
    
    await callback.message.edit_text(message_text)
    await callback.answer()


@user_router.callback_query(F.data == "edit_containers", RouteStates.managing_point_data)
async def edit_containers_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки редактирования контейнеров из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_containers_count)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    current_containers = state_data.get('containers_count', None)
    route_type = state_data.get('route_type', 'collection')
    
    # Формируем сообщение в зависимости от типа маршрута
    if route_type == 'delivery':
        containers_to_deliver = current_point.get('containers_to_deliver', 0)
        point_name = current_point.get('point_name', current_point.get('name', 'Неизвестная точка'))
        message_text = (
            f"📦 Изменение количества контейнеров для отгрузки\n\n"
            f"📍 Точка доставки: <b>{point_name}</b>\n"
            f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
            f"🚚 <b>У вас с собой:</b> {containers_to_deliver} контейнеров\n"
            f"Текущее количество отгружено: {current_containers if current_containers is not None else 'не указано'}\n\n"
            f"Введите новое число от {MIN_CONTAINERS} до {containers_to_deliver}:"
        )
    else:
        message_text = (
            f"📦 Изменение количества контейнеров\n\n"
            f"📍 Точка: <b>{current_point['name']}</b>\n"
            f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
            f"Текущее количество: {current_containers if current_containers is not None else 'не указано'}\n"
            f"Введите новое число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
        )
    
    await callback.message.edit_text(message_text)
    await callback.answer()


@user_router.callback_query(F.data == "add_comment", RouteStates.managing_point_data)
async def add_comment_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки добавления комментария из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_comment)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    
    await callback.message.edit_text(
        f"📝 Добавьте комментарий к точке\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Напишите короткий комментарий (максимум 500 символов):"
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "edit_comment", RouteStates.managing_point_data)
async def edit_comment_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки редактирования комментария из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_comment)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    current_comment = state_data.get('comment', '')
    
    await callback.message.edit_text(
        f"📝 Изменение комментария\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Текущий комментарий: {current_comment}\n\n"
        f"Введите новый комментарий (максимум 500 символов):"
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "continue_route", RouteStates.managing_point_data)
async def continue_route_from_management(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обработчик кнопки "Продолжить маршрут".
    
    Сохраняет всю информацию о точке в базу данных и переходит к следующей точке.
    """
    # Получаем данные состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    selected_city = state_data.get('selected_city')
    current_point_index = state_data.get('current_point_index', 0)
    total_points = state_data.get('total_points', 0)
    collected_containers = state_data.get('collected_containers', {})
    containers_count = state_data.get('containers_count', None)
    comment = state_data.get('comment', '')
    route_session_id = state_data.get('route_session_id')
    
    # Проверяем, что все данные заполнены
    if not photos_list or containers_count is None or not comment:
        await callback.answer("❌ Заполните все необходимые данные!", show_alert=True)
        return
    
    # Сохраняем прогресс в базу данных
    async for session in get_session():
        # Находим или создаём запись маршрута в БД
        stmt = select(Route).where(
            and_(
                Route.city_name == selected_city,
                Route.point_name == current_point['name'],
                Route.organization == current_point['organization']
            )
        )
        route_record = await session.scalar(stmt)
        
        if not route_record:
            # Создаём новую запись маршрута
            coords = current_point.get('coordinates', (None, None))
            lat, lon = coords if isinstance(coords, tuple) else (None, None)

            route_record = Route(
                city_name=selected_city,
                point_name=current_point['name'],
                address=current_point['address'],
                organization=current_point['organization'],
                latitude=lat,
                longitude=lon,
                order_index=current_point_index
            )
            session.add(route_record)
            await session.flush()  # Получаем ID без коммита
        
        # Создаём запись прогресса
        progress = RouteProgress(
            user_id=callback.from_user.id,
            route_id=route_record.id,
            route_session_id=route_session_id,
            containers_count=containers_count,
            notes=comment,
            status='completed'
        )
        session.add(progress)
        await session.flush()  # Получаем ID записи прогресса
        
        # Сохраняем все фотографии
        for index, photo_file_id in enumerate(photos_list, 1):
            photo_record = RoutePhoto(
                route_progress_id=progress.id,
                photo_file_id=photo_file_id,
                photo_order=index
            )
            session.add(photo_record)
        
        await session.commit()
    
    # Обновляем счётчик контейнеров по организациям
    org = current_point['organization']
    collected_containers[org] = collected_containers.get(org, 0) + containers_count
    
    # Увеличиваем счетчик завершенных точек
    completed_points = state_data.get('completed_points', 0) + 1
    
    await state.update_data(
        collected_containers=collected_containers,
        completed_points=completed_points
    )
    
    # Проверяем, есть ли ещё точки в маршруте
    next_point_index = current_point_index + 1
    
    if next_point_index < total_points:
        # Переходим к следующей точке  
        # Используем route_points из состояния, а не AVAILABLE_ROUTES
        route_points = state_data.get('route_points', [])
        if next_point_index < len(route_points):
            next_point = route_points[next_point_index]
        else:
            logger.error(f"next_point_index {next_point_index} превышает количество точек {len(route_points)}")
            await callback.message.answer("❌ Ошибка: неверный индекс точки маршрута")
            return
        
        await state.update_data(
            current_point=next_point,
            current_point_index=next_point_index,
            photos_list=[],  # Очищаем список фотографий для новой точки
            containers_count=None,  # Очищаем количество контейнеров для новой точки
            comment=""  # Очищаем комментарий для новой точки
        )
        
        # Переводим в состояние ожидания фото для следующей точки
        await state.set_state(RouteStates.waiting_for_photo)
        
        point_info = format_route_progress(
            city=selected_city,
            current_point=next_point,
            total_points=total_points,
            current_index=next_point_index,
            collected_containers=collected_containers,
            completed_points=completed_points  # Передаем количество завершенных точек
        )
        point_info = f"✅ Точка завершена! Собрано контейнеров: {containers_count}, фото: {len(photos_list)}\n💬 Комментарий: {comment}\n\n{point_info}\n\n🎯 Выберите действие с данной точкой:"
        
        await callback.message.answer(
            text=point_info,
            reply_markup=get_point_action_keyboard()
        )
        
    else:
        # Все точки пройдены, переходим к завершению маршрута
        await state.set_state(RouteStates.waiting_for_route_completion)
        
        # Получаем тип маршрута
        route_type = state_data.get('route_type', 'collection')
        
        # Формируем сводку по маршруту в зависимости от типа
        if route_type == 'delivery':
            # Для маршрутов доставки в Москву
            summary = f"🎉 <b>Все точки доставки пройдены!</b>\n\n"
            summary += f"✅ <b>Завершено: {completed_points} из {total_points} точек</b>\n"
            summary += f"📊 <b>Сводка по доставке:</b>\n"
            
            total_delivered = 0
            for organization, count in collected_containers.items():
                summary += f"• {organization}: {count} контейнеров\n"
                total_delivered += count
            
            summary += f"\n📦 <b>Всего доставлено:</b> {total_delivered} контейнеров\n\n"
            summary += f"📝 <b>Для завершения маршрута необходимо добавить итоговый комментарий</b>"
        else:
            # Для маршрутов сбора
            summary = f"🎉 <b>Все точки маршрута пройдены!</b>\n\n"
            summary += f"✅ <b>Завершено: {completed_points} из {total_points} точек</b>\n"
            summary += f"📊 <b>Сводка по сбору:</b>\n"
            
            total_collected = 0
            for organization, count in collected_containers.items():
                summary += f"• {organization}: {count} контейнеров\n"
                total_collected += count
            
            summary += f"\n📦 <b>Всего собрано:</b> {total_collected} контейнеров"
        
        await callback.message.answer(
            text=summary,
            reply_markup=get_complete_route_keyboard(route_type)
        )
    
    await callback.answer()


@user_router.callback_query(F.data == "start_lab_summaries", RouteStates.waiting_for_route_completion)
async def start_lab_summaries(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Переход к заполнению итоговых данных по лабораториям.
    
    Анализирует маршрут, определяет уникальные лаборатории и инициализирует
    процесс заполнения дополнительных фотографий и комментариев.
    
    Args:
        callback: Объект callback query
        state: Контекст состояния FSM
    """
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    selected_city = state_data.get('selected_city')
    
    # Получаем все точки маршрута для определения уникальных лабораторий
    route_points = AVAILABLE_ROUTES.get(selected_city, [])
    
    # Определяем уникальные организации
    organizations = {}
    for point in route_points:
        org = point['organization']
        if org not in organizations:
            organizations[org] = {'points_count': 0}
        organizations[org]['points_count'] += 1
    
    # Создаем записи в БД только для тех лабораторий, где есть НЕ ПРОПУЩЕННЫЕ точки
    async for session in get_session():
        # Получаем все записи прогресса для этого маршрута
        route_progresses = await session.scalars(
            select(RouteProgress).options(
                selectinload(RouteProgress.route)
            ).where(
                RouteProgress.route_session_id == route_session_id,
                RouteProgress.user_id == callback.from_user.id
            )
        )
        
        # Группируем по организациям и проверяем, есть ли хотя бы одна НЕ пропущенная точка
        organizations_with_processed_points = {}
        for progress in route_progresses:
            org = progress.route.organization
            # Если точка НЕ пропущена (completed или pending), добавляем организацию
            if hasattr(progress, 'status') and progress.status != 'skipped':
                organizations_with_processed_points[org] = True
            elif not hasattr(progress, 'status'):  # Старые записи без поля status считаем обработанными
                organizations_with_processed_points[org] = True
        
        # Создаем записи только для организаций с обработанными точками
        for organization in organizations_with_processed_points.keys():
            # Проверяем, есть ли уже запись для этой лаборатории
            existing = await session.scalar(
                select(LabSummary).where(
                    LabSummary.route_session_id == route_session_id,
                    LabSummary.organization == organization,
                    LabSummary.user_id == callback.from_user.id
                )
            )
            
            if not existing:
                lab_summary = LabSummary(
                    user_id=callback.from_user.id,
                    route_session_id=route_session_id,
                    organization=organization,
                    is_completed=False
                )
                session.add(lab_summary)
        
        await session.commit()
    
    # Проверяем, остались ли лаборатории для заполнения
    async for session in get_session():
        lab_summaries = await session.scalars(
            select(LabSummary).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.user_id == callback.from_user.id
            )
        )
        lab_summaries_list = lab_summaries.all()
    
    if not lab_summaries_list:
        # Нет лабораторий для заполнения (все точки пропущены), сразу завершаем маршрут
        await complete_route_final(callback, state)
        return
    
    # Переходим в состояние выбора лаборатории
    await state.set_state(RouteStates.selecting_lab_for_summary)
    
    # Показываем список лабораторий
    await show_lab_selection(callback, state)


async def show_lab_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает список лабораторий для заполнения данных."""
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    
    async for session in get_session():
        # Получаем все лаборатории этого маршрута
        stmt = select(LabSummary).options(
            selectinload(LabSummary.summary_photos)
        ).where(
            LabSummary.route_session_id == route_session_id,
            LabSummary.user_id == callback.from_user.id
        )
        
        labs = await session.scalars(stmt)
        labs_list = labs.all()
        
        if not labs_list:
            await callback.message.edit_text(
                "❌ Ошибка: не найдены данные по лабораториям",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Формируем данные для клавиатуры
        labs_data = []
        for lab in labs_list:
            labs_data.append({
                'organization': lab.organization,
                'is_completed': lab.is_completed,
                'points_count': len([p for p in AVAILABLE_ROUTES.get(state_data.get('selected_city', ''), []) 
                                   if p['organization'] == lab.organization])
            })
        
        # Формируем сообщение
        completed_count = sum(1 for lab in labs_data if lab['is_completed'])
        total_count = len(labs_data)
        
        message = f"🏥 <b>Заполнение данных по лабораториям</b>\n\n"
        message += f"📊 Прогресс: {completed_count}/{total_count} лабораторий\n\n"
        message += "Выберите лабораторию для добавления итоговых фотографий и комментариев:\n\n"
        message += "⏳ - не заполнено\n✅ - заполнено"
        
        await callback.message.edit_text(
            text=message,
            reply_markup=get_lab_selection_keyboard(labs_data)
        )
    
    await callback.answer()


# ==============================================
# ОБРАБОТЧИКИ ДЛЯ МАРШРУТОВ В МОСКВУ
# ==============================================

@user_router.callback_query(F.data == "add_final_comment_moscow", RouteStates.waiting_for_route_completion)
async def add_final_comment_moscow(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки добавления итогового комментария для маршрута в Москву.
    """
    await state.set_state(RouteStates.waiting_for_moscow_final_comment)
    
    state_data = await state.get_data()
    collected_containers = state_data.get('collected_containers', {})
    
    # Формируем сводку для отображения
    summary_text = "📝 <b>Добавление итогового комментария</b>\n\n"
    summary_text += "📊 <b>Сводка по доставке:</b>\n"
    
    total_delivered = 0
    for organization, count in collected_containers.items():
        summary_text += f"• {organization}: {count} контейнеров\n"
        total_delivered += count
    
    summary_text += f"\n📦 <b>Всего доставлено:</b> {total_delivered} контейнеров\n\n"
    summary_text += "💬 <b>Напишите итоговый комментарий по завершению маршрута:</b>\n"
    summary_text += "(обязательное поле, максимум 500 символов)"
    
    await callback.message.edit_text(summary_text)
    await callback.answer()


@user_router.message(F.text, RouteStates.waiting_for_moscow_final_comment)
async def moscow_final_comment_received(message: Message, state: FSMContext) -> None:
    """
    Обработчик получения итогового комментария для маршрута в Москву.
    """
    final_comment = message.text.strip()
    
    # Проверяем длину комментария
    if len(final_comment) > 500:
        await message.answer(
            "❌ Комментарий слишком длинный!\n\n"
            "Максимальная длина: 500 символов\n"
            f"Ваш комментарий: {len(final_comment)} символов\n\n"
            "Попробуйте сократить текст:"
        )
        return
    
    if not final_comment:
        await message.answer(
            "❌ Комментарий не может быть пустым!\n\n"
            "Напишите итоговый комментарий по завершению маршрута:"
        )
        return
    
    # Сохраняем комментарий в состоянии
    await state.update_data(moscow_final_comment=final_comment)
    
    state_data = await state.get_data()
    collected_containers = state_data.get('collected_containers', {})
    
    # Показываем подтверждение
    confirmation_text = "✅ <b>Итоговый комментарий добавлен!</b>\n\n"
    confirmation_text += f"💬 <b>Комментарий:</b> {final_comment}\n\n"
    
    confirmation_text += "📊 <b>Сводка по доставке:</b>\n"
    total_delivered = 0
    for organization, count in collected_containers.items():
        confirmation_text += f"• {organization}: {count} контейнеров\n"
        total_delivered += count
    
    confirmation_text += f"\n📦 <b>Всего доставлено:</b> {total_delivered} контейнеров\n\n"
    confirmation_text += "🎯 <b>Нажмите кнопку ниже для завершения маршрута</b>"
    
    await message.answer(
        confirmation_text,
        reply_markup=get_moscow_final_comment_keyboard()
    )


@user_router.callback_query(F.data == "complete_moscow_route_final", RouteStates.waiting_for_moscow_final_comment)
async def complete_moscow_route_final(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Финальное завершение маршрута в Москву с итоговым комментарием.
    """
    state_data = await state.get_data()
    moscow_final_comment = state_data.get('moscow_final_comment', '')
    collected_containers = state_data.get('collected_containers', {})
    moscow_route_id = state_data.get('moscow_route_id')
    
    if not moscow_final_comment:
        await callback.answer("❌ Итоговый комментарий не найден!", show_alert=True)
        return
    
    # Сохраняем итоговый комментарий и обновляем статус маршрута в Москву
    route_session_id = state_data.get('route_session_id')
    
    async for session in get_session():
        # Создаём специальную запись с итоговым комментарием
        final_comment_progress = RouteProgress(
            user_id=callback.from_user.id,
            route_id=1,  # Фиктивный ID для итогового комментария
            route_session_id=route_session_id,
            containers_count=0,  # Не относится к конкретной точке
            notes=f"ИТОГОВЫЙ_КОММЕНТАРИЙ_МОСКВА: {moscow_final_comment}",
            status='completed'
        )
        session.add(final_comment_progress)
        
        # Обновляем статус маршрута в Москву на 'completed'
        if moscow_route_id:
            moscow_route = await session.get(MoscowRoute, moscow_route_id)
            if moscow_route:
                moscow_route.status = 'completed'
                moscow_route.courier_id = callback.from_user.id
                moscow_route.completed_at = datetime.now()
                logger.info(f"Маршрут в Москву {moscow_route_id} помечен как завершенный пользователем {callback.from_user.id}")
                
                # Обновляем статус всех доставок с 'in_progress' на 'completed'
                in_progress_deliveries = await session.scalars(
                    select(Delivery).where(Delivery.status == 'in_progress')
                )
                in_progress_list = in_progress_deliveries.all()
                
                completed_count = 0
                for delivery in in_progress_list:
                    delivery.status = 'completed'
                    delivery.delivered_at = datetime.now()
                    completed_count += 1
                
                logger.info(f"Все доставки in_progress помечены как completed: {completed_count} шт.")
                
            else:
                logger.warning(f"Маршрут в Москву с ID {moscow_route_id} не найден")
        else:
            logger.warning("moscow_route_id не найден в состоянии пользователя")
        
        await session.commit()
    
    # Очищаем состояние
    await state.clear()
    
    # Формируем финальное сообщение
    completion_message = "🎉 <b>Маршрут в Москву успешно завершен!</b>\n\n"
    completion_message += "📊 <b>Итоговая сводка:</b>\n"
    
    total_delivered = 0
    for organization, count in collected_containers.items():
        completion_message += f"• {organization}: {count} контейнеров\n"
        total_delivered += count
    
    completion_message += f"\n📦 <b>Всего доставлено:</b> {total_delivered} контейнеров\n"
    completion_message += f"💬 <b>Итоговый комментарий:</b> {moscow_final_comment}\n\n"
    completion_message += "✅ Все данные сохранены в системе\n"
    completion_message += "🏠 Возвращайтесь в главное меню для выбора нового маршрута"
    
    await callback.message.edit_text(
        completion_message,
        reply_markup=None
    )
    
    # Отправляем главное меню
    await callback.message.answer(
        "🏠 Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer("🎉 Маршрут завершен!")


async def get_user_routes_with_pagination(user_id: int, limit: int = 10, offset: int = 0):
    """
    Получает маршруты пользователя с пагинацией.
    
    Args:
        user_id: ID пользователя
        limit: Количество маршрутов на страницу
        offset: Сдвиг для пагинации
        
    Returns:
        tuple: (routes_data, has_more, total_count)
    """
    async for session in get_session():
        # Получаем все маршруты пользователя с детализацией
        # Сортируем по УБЫВАНИЮ (новые сверху, старые снизу)
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.user_id == user_id
        ).order_by(RouteProgress.visited_at.desc())  # Новые маршруты сверху
        
        routes = await session.scalars(stmt)
        routes_list = routes.all()
        
        if not routes_list:
            return [], False, 0
        
        # Группируем по route_session_id
        routes_summary = {}
        for route_progress in routes_list:
            session_id = route_progress.route_session_id
            date = route_progress.visited_at.strftime("%d.%m.%Y")
            city = route_progress.route.city_name
            
            # Используем session_id как ключ для группировки
            if session_id not in routes_summary:
                # Находим время первой точки этого маршрута
                first_time = min(p.visited_at for p in routes_list if p.route_session_id == session_id)
                time_start = first_time.strftime("%H:%M")
                
                routes_summary[session_id] = {
                    'route_id': session_id,
                    'date': date,
                    'city': city,
                    'time_start': time_start,
                    'first_time': first_time,  # Для сортировки
                    'progresses': []
                }
            
            routes_summary[session_id]['progresses'].append(route_progress)
        
        # Сортируем точки в каждом маршруте по времени
        for route_info in routes_summary.values():
            route_info['progresses'].sort(key=lambda x: x.visited_at)
        
        # Сортируем сами маршруты по времени первой точки (новые сверху)
        sorted_routes = sorted(routes_summary.values(), key=lambda x: x['first_time'], reverse=True)
        
        # Применяем пагинацию
        total_count = len(sorted_routes)
        paginated_routes = sorted_routes[offset:offset + limit]
        has_more = offset + limit < total_count
        
        # Формируем данные для клавиатуры
        routes_data = []
        for route_info in paginated_routes:
            progresses = route_info['progresses']
            total_containers = sum(p.containers_count for p in progresses)
            points_count = len(progresses)
            
            routes_data.append({
                'route_id': route_info['route_id'],
                'date': route_info['date'],
                'city': route_info['city'],
                'points_count': points_count,
                'total_containers': total_containers
            })
        
        return routes_data, has_more, total_count


@user_router.message(F.text == "📊 Мои маршруты")
async def my_routes(message: Message) -> None:
    """
    Показывает историю маршрутов пользователя с группировкой по route_session_id.
    Теперь с пагинацией: сверху новые маршруты, снизу старые по кнопке "еще".
    
    Args:
        message: Объект сообщения от пользователя
    """
    routes_data, has_more, total_count = await get_user_routes_with_pagination(message.from_user.id, limit=10, offset=0)
    
    if not routes_data:
        await message.answer(
            "📭 У вас пока нет пройденных маршрутов",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Формируем ответное сообщение
    response = f"📊 <b>Ваши завершенные маршруты:</b>\n\n"
    response += f"Показано: {len(routes_data)} из {total_count}\n"
    response += "Выберите маршрут для детального просмотра:\n"
    response += "\n🆕 <i>Новые маршруты</i>"
    if has_more:
        response += "\n⬇️ <i>Старые маршруты (нажмите 'Показать еще')</i>"
    
    # Отправляем новое сообщение с клавиатурой
    await message.answer(
        text=response,
        reply_markup=get_route_selection_keyboard(routes_data, has_more, 0)
    )


@user_router.callback_query(F.data.startswith("load_more_routes:"))
async def load_more_routes(callback: CallbackQuery) -> None:
    """
    Обработчик кнопки "Показать еще" для загрузки дополнительных маршрутов.
    
    Args:
        callback: Объект callback query
    """
    # Извлекаем offset из callback_data
    offset = int(callback.data.split(":", 1)[1])
    
    # Получаем дополнительные маршруты
    routes_data, has_more, total_count = await get_user_routes_with_pagination(
        callback.from_user.id, limit=10, offset=offset
    )
    
    if not routes_data:
        await callback.answer("Больше маршрутов нет", show_alert=True)
        return
    
    # Формируем ответное сообщение
    response = f"📊 <b>Ваши завершенные маршруты:</b>\n\n"
    response += f"Показано: {offset + len(routes_data)} из {total_count}\n"
    response += "Выберите маршрут для детального просмотра:\n"
    response += "\n🆕 <i>Новые маршруты</i>"
    if has_more:
        response += "\n⬇️ <i>Старые маршруты (нажмите 'Показать еще')</i>"
    
    # Редактируем сообщение с новыми данными
    await callback.message.edit_text(
        text=response,
        reply_markup=get_route_selection_keyboard(routes_data, has_more, offset)
    )
    
    await callback.answer(f"Загружено еще {len(routes_data)} маршрутов")


# ==============================================
# ОБРАБОТЧИКИ ДЛЯ ПРОСМОТРА ИСТОРИИ МАРШРУТОВ
# ==============================================

@user_router.callback_query(F.data.startswith("r:"))
async def view_route_details(callback: CallbackQuery) -> None:
    """
    Обработчик выбора маршрута для детального просмотра.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'view_route':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    session_id = callback_data['route_id']
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.route_session_id == session_id
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        # Показываем первую точку маршрута
        await show_route_point_details(callback, progresses_list, 0, session_id)
    
    await callback.answer()


async def show_route_point_details(
    callback: CallbackQuery, 
    progresses_list: list, 
    point_index: int, 
    route_id: str
) -> None:
    """
    Показывает детали конкретной точки маршрута.
    """
    if point_index >= len(progresses_list):
        await callback.answer("❌ Точка не найдена", show_alert=True)
        return
    
    progress = progresses_list[point_index]
    route = progress.route
    photos = progress.photos
    
    # Формируем сообщение с деталями точки
    message_text = f"📍 <b>Точка {point_index + 1} из {len(progresses_list)}</b>\n\n"
    message_text += f"🏢 <b>Организация:</b> {route.organization}\n"
    message_text += f"📍 <b>Адрес:</b> {route.address}\n"
    message_text += f"📦 <b>Контейнеров собрано:</b> {progress.containers_count}\n"
    message_text += f"📅 <b>Дата посещения:</b> {progress.visited_at.strftime('%d.%m.%Y %H:%M')}\n"
    
    if progress.notes:
        message_text += f"\n💬 <b>Комментарий:</b> {progress.notes}\n"
    
    # Отображаем информацию о статусе точки
    if hasattr(progress, 'status') and progress.status == 'skipped':
        message_text += f"\n\n⏭️ <b>Статус:</b> Пропущена\n"
        message_text += f"📸 <b>Фотографий:</b> нет (точка пропущена)"
    else:
        if photos:
            message_text += f"\n📸 <b>Фотографий:</b> {len(photos)} шт."
        else:
            message_text += f"\n📸 <b>Фотографий:</b> нет"
    
    # Проверяем наличие итоговых данных по лабораториям для этого маршрута
    async for session in get_session():
        lab_summaries = await session.scalars(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_id,
                LabSummary.user_id == callback.from_user.id
            )
        )
        lab_summaries_list = lab_summaries.all()
    
    # Добавляем информацию о лабораториях, если есть
    has_lab_data = len(lab_summaries_list) > 0
    if has_lab_data:
        completed_labs = sum(1 for lab in lab_summaries_list if lab.is_completed)
        total_labs = len(lab_summaries_list)
        message_text += f"\n\n🏥 <b>Итоговые данные по лабораториям:</b> {completed_labs}/{total_labs}"
    
    # Создаем клавиатуру
    keyboard = get_route_detail_keyboard(
        route_id=route_id,
        current_point_index=point_index,
        total_points=len(progresses_list),
        has_photos=len(photos) > 0,
        has_lab_data=has_lab_data
    )
    
    # Проверяем, является ли текущее сообщение медиа-сообщением
    if callback.message.photo:
        # Если это медиа-сообщение, отправляем новое текстовое сообщение
        await callback.message.answer(
            text=message_text,
            reply_markup=keyboard
        )
    else:
        # Если это текстовое сообщение, редактируем его
        await callback.message.edit_text(
            text=message_text,
            reply_markup=keyboard
        )


@user_router.callback_query(F.data.startswith("rp:"))
async def navigate_route_point(callback: CallbackQuery) -> None:
    """
    Обработчик навигации по точкам маршрута.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'route_point':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    session_id = callback_data['route_id']
    point_index = callback_data['point_index']
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.route_session_id == session_id
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        # Показываем выбранную точку
        await show_route_point_details(callback, progresses_list, point_index, session_id)
    
    await callback.answer()


@user_router.callback_query(F.data.startswith("view_photos:"))
async def view_route_photos(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра фотографий точки маршрута.
    """
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка в данных", show_alert=True)
        return
    
    session_id = parts[1]
    point_index = int(parts[2])
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.route_session_id == session_id
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
        await show_route_photo(callback, photos, 0, session_id, point_index)
    
    await callback.answer()


async def show_route_photo(
    callback: CallbackQuery, 
    photos: list, 
    photo_index: int, 
    route_id: str, 
    point_index: int
) -> None:
    """
    Показывает конкретную фотографию точки маршрута.
    """
    if photo_index >= len(photos):
        await callback.answer("❌ Фотография не найдена", show_alert=True)
        return
    
    photo = photos[photo_index]
    
    # Создаем клавиатуру для навигации по фотографиям
    keyboard = get_photos_viewer_keyboard(
        route_id=route_id,
        point_index=point_index,
        current_photo_index=photo_index,
        total_photos=len(photos)
    )
    
    # Отправляем фотографию с подписью
    caption = f"📸 Фотография {photo_index + 1} из {len(photos)}"
    
    await callback.message.answer_photo(
        photo=photo.photo_file_id,
        caption=caption,
        reply_markup=keyboard
    )


@user_router.callback_query(F.data.startswith("p:"))
async def navigate_route_photo(callback: CallbackQuery) -> None:
    """
    Обработчик навигации по фотографиям точки маршрута.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'view_photo':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    session_id = callback_data['route_id']
    point_index = callback_data['point_index']
    photo_index = callback_data['photo_index']
    
    async for session in get_session():
        # Получаем все точки этого маршрута по session_id
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.route_session_id == session_id
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
        await show_route_photo(callback, photos, photo_index, session_id, point_index)
    
    await callback.answer()


@user_router.callback_query(F.data == "back_to_routes")
async def back_to_routes(callback: CallbackQuery) -> None:
    """
    Обработчик возврата к списку маршрутов.
    """
    # Используем новую функцию с пагинацией
    routes_data, has_more, total_count = await get_user_routes_with_pagination(
        callback.from_user.id, limit=10, offset=0
    )
    
    if not routes_data:
        # Проверяем, является ли текущее сообщение медиа-сообщением
        if callback.message.photo:
            await callback.message.answer(
                "📭 У вас пока нет пройденных маршрутов",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await callback.message.edit_text(
                "📭 У вас пока нет пройденных маршрутов",
                reply_markup=get_main_menu_keyboard()
            )
        await callback.answer()
        return
    
    # Формируем ответное сообщение
    response = f"📊 <b>Ваши завершенные маршруты:</b>\n\n"
    response += f"Показано: {len(routes_data)} из {total_count}\n"
    response += "Выберите маршрут для детального просмотра:\n"
    response += "\n🆕 <i>Новые маршруты</i>"
    if has_more:
        response += "\n⬇️ <i>Старые маршруты (нажмите 'Показать еще')</i>"
    
    # Проверяем, является ли текущее сообщение медиа-сообщением
    if callback.message.photo:
        # Если это медиа-сообщение, отправляем новое текстовое сообщение
        await callback.message.answer(
            text=response,
            reply_markup=get_route_selection_keyboard(routes_data, has_more, 0)
        )
    else:
        # Если это текстовое сообщение, редактируем его
        await callback.message.edit_text(
            text=response,
            reply_markup=get_route_selection_keyboard(routes_data, has_more, 0)
        )
    
    await callback.answer()


@user_router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery) -> None:
    """
    Обработчик возврата в главное меню.
    """
    # Всегда отправляем новое сообщение, так как ReplyKeyboardMarkup нельзя использовать с edit_text
    await callback.message.answer(
        text="🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer()


# ==============================================
# ОБРАБОТЧИКИ ДЛЯ РАБОТЫ С ЛАБОРАТОРИЯМИ
# ==============================================

@user_router.callback_query(F.data.startswith("select_lab:"), RouteStates.selecting_lab_for_summary)
async def select_lab_for_summary(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор лаборатории для заполнения итоговых данных."""
    organization = callback.data.split(":", 1)[1]
    
    # Сохраняем выбранную лабораторию в состоянии
    await state.update_data(selected_lab_organization=organization)
    await state.set_state(RouteStates.managing_lab_summary)
    
    # Показываем интерфейс управления данными лаборатории
    await show_lab_summary_management(callback, state, organization)


async def show_lab_summary_management(callback: CallbackQuery, state: FSMContext, organization: str) -> None:
    """Показывает интерфейс управления данными лаборатории."""
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    
    async for session in get_session():
        # Получаем данные лаборатории
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if not lab_summary:
            await callback.answer("Ошибка: лаборатория не найдена", show_alert=True)
            return
        
        # Получаем текущие данные
        photos_count = len(lab_summary.summary_photos)
        has_photos = photos_count > 0
        has_comment = bool(lab_summary.summary_comment)
        comment_text = lab_summary.summary_comment or ""
        
        # Формируем сообщение
        message = f"🏥 <b>Лаборатория: {organization}</b>\n\n"
        
        if has_photos:
            message += f"📸 Фотографий: {photos_count} ✅\n"
        else:
            message += f"📸 Фотографий: не добавлены ⏳\n"
        
        if has_comment:
            comment_preview = comment_text[:50] + "..." if len(comment_text) > 50 else comment_text
            message += f"📝 Комментарий: {comment_preview} ✅\n"
        else:
            message += f"📝 Комментарий: не добавлен (необязательно)\n"
        
        message += f"\n{'✅ Готово к завершению' if has_photos else '⚠️ Добавьте хотя бы 1 фотографию'}"
        
        await callback.message.edit_text(
            text=message,
            reply_markup=get_lab_summary_management_keyboard(
                has_photos=has_photos,
                has_comment=has_comment,
                photos_count=photos_count,
                comment_text=comment_text,
                organization=organization
            )
        )
    
    await callback.answer()


@user_router.callback_query(F.data == "complete_route_final", RouteStates.selecting_lab_for_summary)
async def complete_route_final(callback: CallbackQuery, state: FSMContext) -> None:
    """Финальное завершение маршрута после заполнения всех лабораторий."""
    state_data = await state.get_data()
    collected_containers = state_data.get('collected_containers', {})
    selected_city = state_data.get('selected_city')
    
    # Создаём доставки для каждой организации
    async for session in get_session():
        for organization, containers_count in collected_containers.items():
            if containers_count > 0:
                delivery_address = MOSCOW_DELIVERY_ADDRESSES.get(organization, {})
                
                delivery = Delivery(
                    organization=organization,
                    total_containers=containers_count,
                    delivery_address=delivery_address.get('address', 'Не указан'),
                    contact_info=delivery_address.get('contact', 'Не указан'),
                    status='pending'
                )
                session.add(delivery)
        
        await session.commit()
    
    # Очищаем состояние
    await state.clear()
    
    # Вычисляем общее время прохождения маршрута
    route_start_time = datetime.fromisoformat(state_data.get('route_start_time'))
    route_end_time = datetime.now()
    total_time = route_end_time - route_start_time
    
    hours = total_time.seconds // 3600
    minutes = (total_time.seconds % 3600) // 60
    time_str = f"{hours}ч {minutes}мин"
    
    # Формируем сообщение с итогами
    # Используем количество точек из состояния, а не AVAILABLE_ROUTES
    route_points = state_data.get('route_points', [])
    completion_message = format_route_summary(
        city=selected_city,
        total_points=len(route_points),
        collected_containers=collected_containers,
        total_time=time_str
    )
    
    # Проверяем, есть ли контейнеры для доставки
    has_containers = any(count > 0 for count in collected_containers.values())
    
    if has_containers:
        completion_message += "\n\n🏥 <b>Итоговые данные по лабораториям заполнены!</b>\n"
        completion_message += "\n📋 Автоматически сформированы задания на доставку в Москву:\n"
    else:
        completion_message += "\n\n⚠️ <b>Все точки маршрута были пропущены!</b>\n"
        completion_message += "\n📋 Нет контейнеров для доставки в Москву.\n"
    
    if has_containers:
        for organization, containers_count in collected_containers.items():
            if containers_count > 0:
                address = MOSCOW_DELIVERY_ADDRESSES.get(organization, {}).get('address', 'Не указан')
                completion_message += f"\n📦 <b>{organization}:</b> {containers_count} контейнеров\n"
                completion_message += f"🏠 Адрес: {address}"
        
        completion_message += "\n\nАдминистраторы получили уведомление о готовности к отправке."
    else:
        completion_message += "\nМаршрут завершен, но никаких контейнеров не было собрано."
    
    await callback.message.edit_text(
        text=completion_message,
        reply_markup=None
    )
    
    await callback.message.answer(
        "🎉 <b>Маршрут полностью завершен!</b>\n\n"
        "Спасибо за отличную работу!",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer("Маршрут завершён!")


@user_router.callback_query(F.data == "add_lab_photos", RouteStates.managing_lab_summary)
async def add_lab_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления фотографий лаборатории."""
    await state.set_state(RouteStates.waiting_for_lab_summary_photos)
    
    await callback.message.edit_text(
        text="📸 <b>Добавление фотографий лаборатории</b>\n\n"
             "Отправьте фотографии лаборатории (от 1 до 10 фото).\n"
             "Это могут быть общие фотографии помещения, оборудования или других важных деталей.",
        reply_markup=get_lab_photos_keyboard(0)
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "edit_lab_photos", RouteStates.managing_lab_summary)
async def edit_lab_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование фотографий лаборатории."""
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    organization = state_data.get('selected_lab_organization')
    
    async for session in get_session():
        # Получаем текущие фотографии
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if lab_summary:
            photos_count = len(lab_summary.summary_photos)
            await state.set_state(RouteStates.waiting_for_lab_summary_photos)
            
            await callback.message.edit_text(
                text=f"📸 <b>Редактирование фотографий лаборатории</b>\n\n"
                     f"Текущее количество фотографий: {photos_count}\n"
                     f"Вы можете добавить еще фотографии или завершить редактирование.",
                reply_markup=get_lab_photos_keyboard(photos_count)
            )
    
    await callback.answer()


@user_router.message(F.photo, RouteStates.waiting_for_lab_summary_photos)
async def handle_lab_photo(message: Message, state: FSMContext) -> None:
    """Обработка фотографий лаборатории."""
    # Отладочная информация
    logger.info(f"📸 handle_lab_photo вызван для пользователя {message.from_user.id}")
    
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    organization = state_data.get('selected_lab_organization')
    
    logger.info(f"📊 State data: route_session_id={route_session_id}, organization={organization}")
    
    if not route_session_id or not organization:
        await message.answer("❌ Ошибка: данные состояния потеряны. Вернитесь к выбору лаборатории.")
        return
    
    async for session in get_session():
        # Находим запись лаборатории
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == message.from_user.id
            )
        )
        
        if not lab_summary:
            await message.answer("❌ Ошибка: лаборатория не найдена")
            return
        
        # Проверяем лимит фотографий
        current_photos_count = len(lab_summary.summary_photos)
        if current_photos_count >= 10:
            await message.answer("❌ Максимум 10 фотографий на лабораторию")
            return
        
        # Получаем лучшее качество фото
        photo = message.photo[-1]
        
        # Создаем запись фотографии
        lab_photo = LabSummaryPhoto(
            lab_summary_id=lab_summary.id,
            photo_file_id=photo.file_id,
            photo_order=current_photos_count + 1
        )
        session.add(lab_photo)
        await session.commit()
        
        new_photos_count = current_photos_count + 1
        
        await message.answer(
            f"✅ Фотография {new_photos_count} добавлена!\n\n"
            f"Всего фотографий: {new_photos_count}/10",
            reply_markup=get_lab_photos_keyboard(new_photos_count)
        )


@user_router.callback_query(F.data == "finish_lab_photos", RouteStates.waiting_for_lab_summary_photos)
async def finish_lab_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """Завершение добавления фотографий."""
    organization = (await state.get_data()).get('selected_lab_organization')
    await state.set_state(RouteStates.managing_lab_summary)
    await show_lab_summary_management(callback, state, organization)


@user_router.callback_query(F.data == "add_more_lab_photos", RouteStates.waiting_for_lab_summary_photos)
async def add_more_lab_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """Продолжение добавления фотографий."""
    await callback.message.edit_text(
        text="📸 <b>Добавление фотографий</b>\n\n"
             "Отправьте следующую фотографию лаборатории.",
        reply_markup=None
    )
    await callback.answer()


@user_router.callback_query(F.data == "add_lab_comment", RouteStates.managing_lab_summary)
async def add_lab_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления комментария к лаборатории."""
    await state.set_state(RouteStates.waiting_for_lab_summary_comment)
    
    await callback.message.edit_text(
        text="📝 <b>Добавление комментария к лаборатории</b>\n\n"
             "Напишите ваш комментарий об этой лаборатории (до 500 символов).\n"
             "Например: особенности работы, замечания, рекомендации.\n\n"
             "Комментарий необязателен - вы можете пропустить этот шаг.",
        reply_markup=get_lab_comment_confirmation_keyboard()
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "edit_lab_comment", RouteStates.managing_lab_summary)
async def edit_lab_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование комментария к лаборатории."""
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    organization = state_data.get('selected_lab_organization')
    
    async for session in get_session():
        # Получаем текущий комментарий
        lab_summary = await session.scalar(
            select(LabSummary).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if lab_summary and lab_summary.summary_comment:
            current_comment = lab_summary.summary_comment
            preview = current_comment[:100] + "..." if len(current_comment) > 100 else current_comment
            
            await state.set_state(RouteStates.waiting_for_lab_summary_comment)
            await callback.message.edit_text(
                text=f"📝 <b>Редактирование комментария</b>\n\n"
                     f"<b>Текущий комментарий:</b>\n{preview}\n\n"
                     f"Отправьте новый комментарий (до 500 символов) или нажмите 'Отменить' для возврата.",
                reply_markup=get_lab_comment_confirmation_keyboard()
            )
        else:
            # Если комментария нет, переходим к добавлению
            await add_lab_comment(callback, state)
    
    await callback.answer()


@user_router.message(F.text, RouteStates.waiting_for_lab_summary_comment)
async def handle_lab_comment(message: Message, state: FSMContext) -> None:
    """Обработка комментария к лаборатории."""
    comment_text = message.text.strip()
    
    # Проверяем длину комментария
    if len(comment_text) > 500:
        # Сохраняем состояние для повторного ввода
        await state.set_state(RouteStates.waiting_for_lab_summary_comment)
        await message.answer(
            f"❌ Комментарий слишком длинный!\n"
            f"Максимум 500 символов, у вас: {len(comment_text)}\n\n"
            f"Сократите текст и отправьте заново."
        )
        return
    
    # Сохраняем комментарий в состоянии для подтверждения
    await state.update_data(pending_lab_comment=comment_text)
    
    preview = comment_text[:100] + "..." if len(comment_text) > 100 else comment_text
    
    await message.answer(
        f"📝 <b>Подтверждение комментария:</b>\n\n"
        f"{preview}\n\n"
        f"Символов: {len(comment_text)}/500",
        reply_markup=get_lab_comment_confirmation_keyboard()
    )


@user_router.callback_query(F.data == "save_lab_comment", RouteStates.waiting_for_lab_summary_comment)
async def save_lab_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохранение комментария к лаборатории."""
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    organization = state_data.get('selected_lab_organization')
    comment_text = state_data.get('pending_lab_comment', '')
    
    async for session in get_session():
        # Находим запись лаборатории
        lab_summary = await session.scalar(
            select(LabSummary).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if lab_summary:
            lab_summary.summary_comment = comment_text
            await session.commit()
    
    await state.set_state(RouteStates.managing_lab_summary)
    await show_lab_summary_management(callback, state, organization)


@user_router.callback_query(F.data == "cancel_lab_comment", RouteStates.waiting_for_lab_summary_comment)
async def cancel_lab_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена добавления комментария."""
    organization = (await state.get_data()).get('selected_lab_organization')
    await state.set_state(RouteStates.managing_lab_summary)
    await show_lab_summary_management(callback, state, organization)


@user_router.callback_query(F.data.startswith("complete_lab:"), RouteStates.managing_lab_summary)
async def complete_lab_summary(callback: CallbackQuery, state: FSMContext) -> None:
    """Завершение заполнения данных по лаборатории."""
    organization = callback.data.split(":", 1)[1]
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    
    async for session in get_session():
        # Проверяем, что есть хотя бы одно фото
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if not lab_summary:
            await callback.answer("Ошибка: лаборатория не найдена", show_alert=True)
            return
        
        photos_count = len(lab_summary.summary_photos)
        if photos_count == 0:
            await callback.answer("⚠️ Добавьте хотя бы одну фотографию лаборатории!", show_alert=True)
            return
        
        # Отмечаем лабораторию как завершенную
        lab_summary.is_completed = True
        await session.commit()
    
    await state.set_state(RouteStates.selecting_lab_for_summary)
    await show_lab_selection(callback, state)


@user_router.callback_query(F.data == "back_to_lab_selection", RouteStates.managing_lab_summary)
async def back_to_lab_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к списку лабораторий."""
    await state.set_state(RouteStates.selecting_lab_for_summary)
    await show_lab_selection(callback, state)


@user_router.callback_query(F.data == "add_first_lab_photo", RouteStates.waiting_for_lab_summary_photos)
async def add_first_lab_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления первой фотографии лаборатории."""
    user_id = callback.from_user.id
    logger.info(f"🔥 add_first_lab_photo вызван для пользователя {user_id}")
    
    # Переходим в состояние ожидания фото
    await state.set_state(RouteStates.waiting_for_lab_summary_photos)
    logger.info(f"🎯 Переход в состояние waiting_for_lab_summary_photos")
    
    await callback.message.edit_text(
        text="📸 <b>Добавление первой фотографии</b>\n\n"
             "Отправьте первую фотографию лаборатории.\n"
             "После отправки вы сможете добавить до 9 дополнительных фотографий.",
        reply_markup=None
    )
    await callback.answer()


@user_router.callback_query(F.data == "remove_last_lab_photo", RouteStates.waiting_for_lab_summary_photos)
async def remove_last_lab_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """Удаление последней фотографии лаборатории."""
    state_data = await state.get_data()
    route_session_id = state_data.get('route_session_id')
    organization = state_data.get('selected_lab_organization')
    
    async for session in get_session():
        # Находим запись лаборатории
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_session_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if not lab_summary:
            await callback.answer("Ошибка: лаборатория не найдена", show_alert=True)
            return
        
        # Находим последнюю фотографию
        photos = sorted(lab_summary.summary_photos, key=lambda x: x.photo_order, reverse=True)
        if photos:
            last_photo = photos[0]
            await session.delete(last_photo)
            await session.commit()
            
            remaining_count = len(photos) - 1
            await callback.message.edit_text(
                text=f"🗑 Последняя фотография удалена!\n\n"
                     f"Осталось фотографий: {remaining_count}/10",
                reply_markup=get_lab_photos_keyboard(remaining_count)
            )
        else:
            await callback.answer("Нет фотографий для удаления", show_alert=True)
    
    await callback.answer()


# ==============================================
# ОБРАБОТЧИКИ ОБРАБОТКИ И ПРОПУСКА ТОЧЕК МАРШРУТА
# ==============================================

@user_router.callback_query(F.data == "process_point", RouteStates.waiting_for_photo)
async def process_point(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки 'Обработать точку'.
    
    Переводит пользователя к загрузке фотографий.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    
    if not current_point:
        await callback.answer("❌ Ошибка: точка не найдена", show_alert=True)
        return
    
    # Переходим к загрузке фото
    point_info = (
        f"📍 <b>Обработка точки:</b>\n\n"
        f"🏢 <b>Организация:</b> {current_point['organization']}\n"
        f"🏠 <b>Адрес:</b> {current_point['address']}\n\n"
        f"📸 Отправьте фотографию с данной точки"
    )
    
    await callback.message.edit_text(
        text=point_info,
        reply_markup=None
    )
    await callback.answer("📸 Отправьте фотографию")


@user_router.callback_query(F.data == "skip_point", RouteStates.waiting_for_photo)
async def skip_point(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки 'Пропустить точку'.
    
    Пропускает текущую точку и переходит к следующей.
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    route_points = state_data.get('route_points', [])
    current_point_index = state_data.get('current_point_index', 0)
    selected_city = state_data.get('selected_city')
    route_session_id = state_data.get('route_session_id')
    collected_containers = state_data.get('collected_containers', {})
    completed_points = state_data.get('completed_points', 0)
    
    if not current_point or not route_session_id:
        await callback.answer("❌ Ошибка: данные маршрута не найдены", show_alert=True)
        return
    
    # Сохраняем пропущенную точку в базу данных
    from database.models import Route, RouteProgress
    from database.database import get_session
    from sqlalchemy import select
    
    async for session in get_session():
        # Находим соответствующую запись в таблице routes
        stmt = select(Route).where(
            Route.city_name == selected_city,
            Route.organization == current_point['organization'],
            Route.point_name == current_point['name']
        )
        route_record = await session.scalar(stmt)
        
        if route_record:
            # Создаем запись о пропущенной точке
            progress_record = RouteProgress(
                user_id=callback.from_user.id,
                route_id=route_record.id,
                route_session_id=route_session_id,
                containers_count=0,  # Пропущенная точка - 0 контейнеров
                status='skipped',  # Отмечаем как пропущенную
                notes=f"Точка пропущена пользователем"
            )
            session.add(progress_record)
            await session.commit()
    
    # Переходим к следующей точке
    next_point_index = current_point_index + 1
    
    if next_point_index < len(route_points):
        # Переходим к следующей точке
        next_point = route_points[next_point_index]
        
        # Обновляем состояние
        await state.update_data(
            current_point=next_point,
            current_point_index=next_point_index,
            completed_points=completed_points + 1  # Увеличиваем счетчик (пропущенная = обработанная)
        )
        
        # Показываем следующую точку
        point_info = format_route_progress(
            city=selected_city,
            current_point=next_point,
            total_points=len(route_points),
            current_index=next_point_index,
            collected_containers=collected_containers,
            completed_points=completed_points + 1
        )
        point_info += "\n\n🎯 Выберите действие с данной точкой:"
        
        await callback.message.edit_text(
            text=point_info,
            reply_markup=get_point_action_keyboard()
        )
        await callback.answer(f"⏭️ Точка пропущена! Переход к следующей")
        
    else:
        # Все точки пройдены, переходим к завершению маршрута
        await state.set_state(RouteStates.waiting_for_route_completion)
        
        # Получаем тип маршрута
        route_type = state_data.get('route_type', 'collection')
        
        if route_type == 'delivery':
            # Для маршрутов доставки в Москву
            await callback.message.edit_text(
                text=f"🏁 <b>Маршрут доставки завершен!</b>\n\n"
                     f"📍 Последняя точка пропущена\n"
                     f"📅 Время завершения: {datetime.now().strftime('%H:%M')}\n\n"
                     f"📝 Для полного завершения необходимо добавить итоговый комментарий.",
                reply_markup=get_complete_route_keyboard(route_type)
            )
        else:
            # Для маршрутов сбора
            await callback.message.edit_text(
                text=f"🏁 <b>Маршрут завершен!</b>\n\n"
                     f"📍 Последняя точка пропущена\n"
                     f"📅 Время завершения: {datetime.now().strftime('%H:%M')}\n\n"
                     f"Для полного завершения нужно заполнить \n"
                     f"итоговые данные по лабораториям.",
                reply_markup=get_complete_route_keyboard(route_type)
            )
        
        await callback.answer("🏁 Маршрут завершен!")


# ==============================================
# ОБРАБОТЧИКИ ДЛЯ ПРОСМОТРА ДАННЫХ ЛАБОРАТОРИЙ В МАРШРУТАХ
# ==============================================

@user_router.callback_query(F.data.startswith("ld:"))
async def view_route_lab_data(callback: CallbackQuery) -> None:
    """
    Отображает список лабораторий с их итоговыми данными.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'view_lab_data':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    route_id = callback_data['route_id']
    logger.info(f"🏥 view_route_lab_data вызван для маршрута {route_id}")
    
    async for session in get_session():
        # Получаем все лаборатории этого маршрута
        stmt = select(LabSummary).options(
            selectinload(LabSummary.summary_photos)
        ).where(
            LabSummary.route_session_id == route_id,
            LabSummary.user_id == callback.from_user.id
        )
        
        labs = await session.scalars(stmt)
        labs_list = labs.all()
        
        if not labs_list:
            await callback.answer("❌ Лабораторные данные не найдены", show_alert=True)
            return
        
        # Формируем данные для клавиатуры
        labs_data = []
        for lab in labs_list:
            labs_data.append({
                'organization': lab.organization,
                'photos_count': len(lab.summary_photos),
                'has_comment': bool(lab.summary_comment)
            })
        
        # Формируем сообщение
        message_text = f"🏥 <b>Итоговые данные по лабораториям</b>\n\n"
        
        for lab_data in labs_data:
            organization = lab_data['organization']
            photos_count = lab_data['photos_count']
            has_comment = lab_data['has_comment']
            
            message_text += f"🏢 <b>{organization}</b>\n"
            message_text += f"   📸 Фотографий: {photos_count}\n"
            message_text += f"   📝 Комментарий: {'\u2705' if has_comment else '\u2796'}\n\n"
        
        message_text += "👆 Нажмите на лабораторию для просмотра фотографий и комментариев"
        
        # Создаем клавиатуру
        keyboard = get_route_lab_data_keyboard(route_id, labs_data)
        
        # Проверяем, является ли текущее сообщение медиа-сообщением
        if callback.message.photo:
            # Если это медиа-сообщение, отправляем новое текстовое сообщение
            await callback.message.answer(
                text=message_text,
                reply_markup=keyboard
            )
        else:
            # Если это текстовое сообщение, редактируем его
            await callback.message.edit_text(
                text=message_text,
                reply_markup=keyboard
            )
    
    await callback.answer()


@user_router.callback_query(F.data.startswith("sl:"))
async def view_specific_lab_data(callback: CallbackQuery) -> None:
    """
    Отображает данные конкретной лаборатории.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'view_route_lab':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    route_id = callback_data['route_id']
    organization = callback_data['organization']
    
    logger.info(f"🏥 view_specific_lab_data вызван для {organization} в маршруте {route_id}")
    
    async for session in get_session():
        # Получаем данные лаборатории
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if not lab_summary:
            await callback.answer("❌ Лаборатория не найдена", show_alert=True)
            return
        
        photos = lab_summary.summary_photos
        total_photos = len(photos)
        has_comment = bool(lab_summary.summary_comment)
        
        if total_photos > 0:
            # Показываем первую фотографию
            await show_lab_photo(callback, route_id, organization, 0)
        else:
            # Нет фотографий, показываем только комментарий (если есть)
            message_text = f"🏥 <b>{organization}</b>\n\n"
            
            if has_comment:
                message_text += f"📝 <b>Комментарий:</b>\n{lab_summary.summary_comment}\n\n"
            else:
                message_text += "📝 Комментарий не добавлен\n\n"
            
            message_text += "📸 Фотографии не добавлены"
            
            keyboard = get_lab_data_viewer_keyboard(
                route_id=route_id,
                organization=organization,
                current_photo_index=0,
                total_photos=0,
                has_comment=has_comment
            )
            
            await callback.message.edit_text(
                text=message_text,
                reply_markup=keyboard
            )
    
    await callback.answer()


async def show_lab_photo(
    callback: CallbackQuery,
    route_id: str,
    organization: str,
    photo_index: int
) -> None:
    """
    Показывает конкретную фотографию лаборатории.
    """
    async for session in get_session():
        lab_summary = await session.scalar(
            select(LabSummary).options(
                selectinload(LabSummary.summary_photos)
            ).where(
                LabSummary.route_session_id == route_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if not lab_summary or not lab_summary.summary_photos:
            await callback.answer("❌ Фотографии не найдены", show_alert=True)
            return
        
        photos = sorted(lab_summary.summary_photos, key=lambda x: x.photo_order)
        total_photos = len(photos)
        
        if photo_index >= total_photos:
            await callback.answer("❌ Фотография не найдена", show_alert=True)
            return
        
        photo = photos[photo_index]
        has_comment = bool(lab_summary.summary_comment)
        
        # Формируем подпись
        caption = f"🏥 <b>{organization}</b>\n\n"
        caption += f"📸 Фотография {photo_index + 1} из {total_photos}\n\n"
        
        if photo.description:
            caption += f"📝 Описание: {photo.description}\n\n"
        
        # Создаем клавиатуру
        keyboard = get_lab_data_viewer_keyboard(
            route_id=route_id,
            organization=organization,
            current_photo_index=photo_index,
            total_photos=total_photos,
            has_comment=has_comment
        )
        
        # Отправляем фотографию
        await callback.message.answer_photo(
            photo=photo.photo_file_id,
            caption=caption,
            reply_markup=keyboard
        )


@user_router.callback_query(F.data.startswith("lp:"))
async def navigate_lab_photo(callback: CallbackQuery) -> None:
    """
    Навигация по фотографиям лаборатории.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'lab_photo':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    route_id = callback_data['route_id']
    organization = callback_data['organization']
    photo_index = callback_data['photo_index']
    
    logger.info(f"📸 navigate_lab_photo: {organization}, фото {photo_index}")
    
    await show_lab_photo(callback, route_id, organization, photo_index)
    await callback.answer()


@user_router.callback_query(F.data.startswith("lc:"))
async def show_lab_comment(callback: CallbackQuery) -> None:
    """
    Показывает комментарий лаборатории.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'lab_comment':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    route_id = callback_data['route_id']
    organization = callback_data['organization']
    
    logger.info(f"📝 show_lab_comment: {organization}")
    
    async for session in get_session():
        lab_summary = await session.scalar(
            select(LabSummary).where(
                LabSummary.route_session_id == route_id,
                LabSummary.organization == organization,
                LabSummary.user_id == callback.from_user.id
            )
        )
        
        if not lab_summary or not lab_summary.summary_comment:
            await callback.answer("❌ Комментарий не найден", show_alert=True)
            return
        
        # Формируем сообщение с комментарием
        message_text = f"🏥 <b>{organization}</b>\n\n"
        message_text += f"📝 <b>Комментарий:</b>\n\n"
        message_text += f"{lab_summary.summary_comment}"
        
        # Кнопка возврата
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=create_specific_lab_callback(route_id, organization)
                )
            ]]
        )
        
        # Проверяем тип сообщения
        if callback.message.photo:
            # Если это медиа-сообщение, отправляем новое
            await callback.message.answer(
                text=message_text,
                reply_markup=keyboard
            )
        else:
            # Если это текстовое сообщение, редактируем
            await callback.message.edit_text(
                text=message_text,
                reply_markup=keyboard
            )
    
    await callback.answer()


@user_router.callback_query(F.data.startswith("br:"))
async def back_to_route_details(callback: CallbackQuery) -> None:
    """
    Возвращает к деталям маршрута.
    """
    callback_data = parse_callback(callback.data)
    if not callback_data or callback_data.get('action') != 'back_to_route':
        await callback.answer("Ошибка: неверные данные", show_alert=True)
        return
    
    route_id = callback_data['route_id']
    point_index = callback_data.get('point_index', 0)
    
    logger.info(f"⬅️ back_to_route_details: {route_id}, точка {point_index}")
    
    # Получаем все точки маршрута
    async for session in get_session():
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.route_session_id == route_id
        ).order_by(RouteProgress.visited_at)
        
        progresses = await session.scalars(stmt)
        progresses_list = progresses.all()
        
        if not progresses_list:
            await callback.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        # Показываем детали точки маршрута
        await show_route_point_details(callback, progresses_list, point_index, route_id)
    
    await callback.answer()


# ==============================================
# ОБЩИЙ ОБРАБОТЧИК ДЛЯ НЕОПОЗНАННЫХ СООБЩЕНИЙ
# (ДОЛЖЕН БЫТЬ В САМОМ КОНЦЕ!)
# ==============================================

@user_router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    """
    Обработчик для всех неопознанных сообщений.
    
    Помогает пользователю вернуться к нормальному взаимодействию с ботом.
    
    Args:
        message: Объект неопознанного сообщения
        state: Контекст состояния FSM
    """
    current_state = await state.get_state()
    
    # Отладочная информация
    logger.info(f"🤔 unknown_message для пользователя {message.from_user.id}")
    logger.info(f"📱 Тип сообщения: {message.content_type}")
    logger.info(f"🎯 Текущее состояние: {current_state}")
    
    if message.photo:
        logger.info(f"📸 Получена фотография, но не обработана специальным обработчиком")
    
    if current_state == RouteStates.waiting_for_photo:
        await message.answer(ERROR_MESSAGES['photo_required'])
    elif current_state == RouteStates.waiting_for_additional_photos:
        await message.answer("📸 Отправьте фотографию или воспользуйтесь кнопками выше")
    elif current_state == RouteStates.waiting_for_lab_summary_photos:
        if message.photo:
            logger.info(f"📸 Фотография получена в состоянии waiting_for_lab_summary_photos, но не обработана handle_lab_photo")
            await message.answer("⚠️ Фотография не была обработана. Попробуйте еще раз.")
        else:
            await message.answer("📸 Отправьте фотографию лаборатории.")
    elif current_state == RouteStates.waiting_for_containers_count:
        await message.answer(ERROR_MESSAGES['invalid_containers_count'])
    elif current_state == RouteStates.waiting_for_comment:
        await message.answer("📝 Напишите короткий комментарий к этой точке маршрута (максимум 500 символов)")
    elif current_state == RouteStates.managing_point_data:
        await message.answer("🔄 Используйте кнопки выше для управления данными точки")
    elif current_state == RouteStates.waiting_for_moscow_final_comment:
        await message.answer("💬 Напишите итоговый комментарий по завершению маршрута в Москву (обязательное поле, максимум 500 символов)")
    else:
        await message.answer(
            "🤔 Я не понимаю это сообщение. Используйте кнопки меню или команды.",
            reply_markup=get_main_menu_keyboard()
        )
