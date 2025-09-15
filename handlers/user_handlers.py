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
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from utils.progress_bar import format_route_progress, format_route_summary

# Импорты наших модулей
from database.database import get_session
from database.models import User, Route, RouteProgress, Delivery, RoutePhoto
from utils.callback_manager import parse_callback
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
    get_photos_viewer_keyboard
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
    
    await message.answer(
        "🏙️ Выберите город для маршрута:",
        reply_markup=get_cities_keyboard()
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
    
    # Проверяем, что город существует в конфигурации
    if city_name not in AVAILABLE_ROUTES:
        await callback.answer("❌ Неизвестный город", show_alert=True)
        return
    
    # Получаем точки маршрута для выбранного города
    route_points = AVAILABLE_ROUTES[city_name]
    
    # Сохраняем выбранный город и маршрут
    await state.update_data(
        selected_city=city_name,
        route_points=route_points,
        current_point_index=0,
        collected_containers={},
        completed_points=0  # Добавляем счетчик завершенных точек
    )
    
    # Переводим в состояние ожидания подтверждения
    await state.set_state(RouteStates.waiting_for_route_confirmation)
    
    # Формируем информацию о маршруте
    route_info = f"📍 <b>Выбранный маршрут: {city_name}</b>\n\n"
    route_info += f"📋 <b>Точки для посещения ({len(route_points)}):</b>\n"
    
    for i, point in enumerate(route_points, 1):
        route_info += f"{i}. <b>{point['organization']}</b> - {point['name']}\n"
        route_info += f"   📍 {point['address']}\n\n"
    
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
    point_info += "\n\n📸 Сделайте фотографию в данной точке"
    
    await callback.message.edit_text(
        text=point_info,
        reply_markup=None
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
            f"📸 Сделайте фотографию в данной точке"
        )
        
        await callback.message.edit_text(
            text=point_info,
            reply_markup=None
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
            containers_count=0,
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
    
    # Переводим в состояние ожидания количества контейнеров
    await state.set_state(RouteStates.waiting_for_containers_count)
    
    await callback.message.edit_text(
        f"📦 Фотографии сохранены!\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Укажите количество собранных контейнеров\n"
        f"Введите число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
    )
    
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
    containers_count = state_data.get('containers_count', 0)
    comment = state_data.get('comment', '')
    
    # Переводим в состояние управления данными точки
    await state.set_state(RouteStates.managing_point_data)
    
    status_text = _get_point_status_text(state_data, current_point)
    
    await callback.message.edit_text(
        status_text,
        reply_markup=get_point_data_management_keyboard(
            has_photos=len(photos_list) > 0,
            has_containers=containers_count >= 0,
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
        await message.answer(
            f"❌ Введите корректное число от {MIN_CONTAINERS} до {MAX_CONTAINERS}"
        )
        return
    
    # Проверяем диапазон
    if containers_count < MIN_CONTAINERS or containers_count > MAX_CONTAINERS:
        await message.answer(ERROR_MESSAGES['invalid_containers_count'])
        return
    
    # Получаем данные состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    selected_city = state_data.get('selected_city')
    current_point_index = state_data.get('current_point_index', 0)
    total_points = state_data.get('total_points', 0)
    collected_containers = state_data.get('collected_containers', {})
    
    # Сохраняем количество контейнеров в состоянии и возвращаемся к управлению данными
    await state.update_data(containers_count=containers_count)
    await state.set_state(RouteStates.managing_point_data)
    
    # Получаем обновленные данные для отображения статуса
    state_data = await state.get_data()
    photos_list = state_data.get('photos_list', [])
    comment = state_data.get('comment', '')
    
    status_text = _get_point_status_text(state_data, current_point)
    
    await message.answer(
        f"✅ Количество контейнеров сохранено: {containers_count}\n\n" + status_text,
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
        await message.answer("❌ Комментарий слишком длинный. Максимальная длина: 500 символов")
        return
    
    # Получаем данные состояния
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    containers_count = state_data.get('containers_count', 0)
    
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
            has_containers=containers_count >= 0,
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
    containers_count = state_data.get('containers_count', 0)
    comment = state_data.get('comment', '')
    
    status_text = f"📍 Точка: <b>{current_point['name']}</b>\n"
    status_text += f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
    status_text += "📊 Статус заполнения:\n"
    status_text += f"📸 Фото: {'✅' if photos_list else '❌'} ({len(photos_list)} шт.)\n"
    status_text += f"📦 Контейнеры: {'✅' if containers_count >= 0 else '❌'} ({containers_count} шт.)\n"
    status_text += f"📝 Комментарий: {'✅' if comment else '❌'}\n\n"
    
    if photos_list and containers_count >= 0 and comment:
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
    
    await callback.message.edit_text(
        f"📦 Укажите количество собранных контейнеров\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Введите число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
    )
    
    await callback.answer()


@user_router.callback_query(F.data == "edit_containers", RouteStates.managing_point_data)
async def edit_containers_from_management(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки редактирования контейнеров из меню управления данными.
    """
    await state.set_state(RouteStates.waiting_for_containers_count)
    
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    current_containers = state_data.get('containers_count', 0)
    
    await callback.message.edit_text(
        f"📦 Изменение количества контейнеров\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Текущее количество: {current_containers}\n"
        f"Введите новое число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
    )
    
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
    containers_count = state_data.get('containers_count', 0)
    comment = state_data.get('comment', '')
    route_session_id = state_data.get('route_session_id')
    
    # Проверяем, что все данные заполнены
    if not photos_list or containers_count < 0 or not comment:
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
        route_points = AVAILABLE_ROUTES[selected_city]
        next_point = route_points[next_point_index]
        
        await state.update_data(
            current_point=next_point,
            current_point_index=next_point_index,
            photos_list=[],  # Очищаем список фотографий для новой точки
            containers_count=0,  # Очищаем количество контейнеров для новой точки
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
        point_info = f"✅ Точка завершена! Собрано контейнеров: {containers_count}, фото: {len(photos_list)}\n💬 Комментарий: {comment}\n\n{point_info}\n\n📸 Сделайте фотографию в данной точке"
        
        await callback.message.answer(point_info)
        
    else:
        # Все точки пройдены, переходим к завершению маршрута
        await state.set_state(RouteStates.waiting_for_route_completion)
        
        # Формируем сводку по маршруту
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
            reply_markup=get_complete_route_keyboard()
        )
    
    await callback.answer()


@user_router.callback_query(F.data == "complete_route", RouteStates.waiting_for_route_completion)
async def complete_route(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Завершение маршрута и формирование заданий для доставки в Москву.
    
    Создаёт записи доставок для каждой организации и отправляет
    уведомления администраторам.
    
    Args:
        callback: Объект callback query от кнопки завершения
        state: Контекст состояния FSM
    """
    state_data = await state.get_data()
    collected_containers = state_data.get('collected_containers', {})
    selected_city = state_data.get('selected_city')
    
    # Создаём доставки для каждой организации
    async for session in get_session():
        for organization, containers_count in collected_containers.items():
            if containers_count > 0:  # Создаём доставку только если есть контейнеры
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
    
    # Форматируем время в удобный вид
    hours = total_time.seconds // 3600
    minutes = (total_time.seconds % 3600) // 60
    time_str = f"{hours}ч {minutes}мин"
    
    # Формируем сообщение с итогами маршрута
    completion_message = format_route_summary(
        city=selected_city,
        total_points=len(AVAILABLE_ROUTES[selected_city]),
        collected_containers=collected_containers,
        total_time=time_str
    )
    
    completion_message += "\n\n📋 Автоматически сформированы задания на доставку в Москву:\n"
    
    for organization, containers_count in collected_containers.items():
        if containers_count > 0:
            address = MOSCOW_DELIVERY_ADDRESSES.get(organization, {}).get('address', 'Не указан')
            completion_message += f"\n📦 <b>{organization}:</b> {containers_count} контейнеров\n"
            completion_message += f"🏠 Адрес: {address}"
    
    completion_message += "\n\nАдминистраторы получили уведомление о готовности к отправке."
    
    await callback.message.edit_text(
        text=completion_message,
        reply_markup=None
    )
    
    # Отправляем уведомление в главное меню
    await callback.message.answer(
        "🏠 Возвращайтесь в главное меню для выбора нового маршрута",
        reply_markup=get_main_menu_keyboard()
    )
    
    await callback.answer("Маршрут завершён!")


@user_router.message(F.text == "📊 Мои маршруты")
async def my_routes(message: Message) -> None:
    """
    Показывает историю маршрутов пользователя с группировкой по route_session_id.
    
    Args:
        message: Объект сообщения от пользователя
    """
    async for session in get_session():
        # Получаем все маршруты пользователя с детализацией
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.user_id == message.from_user.id
        ).order_by(RouteProgress.visited_at.desc())
        
        routes = await session.scalars(stmt)
        routes_list = routes.all()
        
        if not routes_list:
            await message.answer(
                "📭 У вас пока нет пройденных маршрутов",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
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
                    'progresses': []
                }
            
            routes_summary[session_id]['progresses'].append(route_progress)
        
        # Сортируем точки в каждом маршруте по времени
        for route_info in routes_summary.values():
            route_info['progresses'].sort(key=lambda x: x.visited_at)
        
        # Формируем данные для клавиатуры
        routes_data = []
        for session_id, route_info in list(routes_summary.items())[:10]:  # Ограничиваем 10 маршрутами
            progresses = route_info['progresses']
            total_containers = sum(p.containers_count for p in progresses)
            points_count = len(progresses)
            
            routes_data.append({
                'route_id': session_id,  # Используем session_id как route_id
                'date': route_info['date'],
                'city': route_info['city'],
                'points_count': points_count,
                'total_containers': total_containers
            })
        
        # Формируем ответное сообщение
        response = "📊 <b>Ваши завершенные маршруты:</b>\n\n"
        response += "Выберите маршрут для детального просмотра:\n"
        
        # Отправляем новое сообщение с клавиатурой
        await message.answer(
            text=response,
            reply_markup=get_route_selection_keyboard(routes_data)
        )


# Обработчик для неопознанных сообщений
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
    
    if current_state == RouteStates.waiting_for_photo:
        await message.answer(ERROR_MESSAGES['photo_required'])
    elif current_state == RouteStates.waiting_for_additional_photos:
        await message.answer("📸 Отправьте фотографию или воспользуйтесь кнопками выше")
    elif current_state == RouteStates.waiting_for_containers_count:
        await message.answer(ERROR_MESSAGES['invalid_containers_count'])
    elif current_state == RouteStates.waiting_for_comment:
        await message.answer("📝 Напишите короткий комментарий к этой точке маршрута (максимум 500 символов)")
    elif current_state == RouteStates.managing_point_data:
        await message.answer("🔄 Используйте кнопки выше для управления данными точки")
    else:
        await message.answer(
            "🤔 Я не понимаю это сообщение. Используйте кнопки меню или команды.",
            reply_markup=get_main_menu_keyboard()
        )


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
    
    if photos:
        message_text += f"\n📸 <b>Фотографий:</b> {len(photos)} шт."
    else:
        message_text += f"\n📸 <b>Фотографий:</b> нет"
    
    # Создаем клавиатуру
    keyboard = get_route_detail_keyboard(
        route_id=route_id,
        current_point_index=point_index,
        total_points=len(progresses_list),
        has_photos=len(photos) > 0
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
    # Получаем данные маршрутов напрямую
    async for session in get_session():
        # Получаем все маршруты пользователя с детализацией
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route),
            selectinload(RouteProgress.photos)
        ).where(
            RouteProgress.user_id == callback.from_user.id
        ).order_by(RouteProgress.visited_at.desc())
        
        routes = await session.scalars(stmt)
        routes_list = routes.all()
        
        if not routes_list:
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
                    'progresses': []
                }
            
            routes_summary[session_id]['progresses'].append(route_progress)
        
        # Сортируем точки в каждом маршруте по времени
        for route_info in routes_summary.values():
            route_info['progresses'].sort(key=lambda x: x.visited_at)
        
        # Формируем данные для клавиатуры
        routes_data = []
        for session_id, route_info in list(routes_summary.items())[:10]:  # Ограничиваем 10 маршрутами
            progresses = route_info['progresses']
            total_containers = sum(p.containers_count for p in progresses)
            points_count = len(progresses)
            
            routes_data.append({
                'route_id': session_id,  # Используем session_id как route_id
                'date': route_info['date'],
                'city': route_info['city'],
                'points_count': points_count,
                'total_containers': total_containers
            })
        
        # Формируем ответное сообщение
        response = "📊 <b>Ваши завершенные маршруты:</b>\n\n"
        response += "Выберите маршрут для детального просмотра:\n"
        
        # Проверяем, является ли текущее сообщение медиа-сообщением
        if callback.message.photo:
            # Если это медиа-сообщение, отправляем новое текстовое сообщение
            await callback.message.answer(
                text=response,
                reply_markup=get_route_selection_keyboard(routes_data)
            )
        else:
            # Если это текстовое сообщение, редактируем его
            await callback.message.edit_text(
                text=response,
                reply_markup=get_route_selection_keyboard(routes_data)
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
