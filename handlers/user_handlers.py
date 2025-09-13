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
from states.user_states import RouteStates
from keyboards.user_keyboards import (
    get_main_menu_keyboard,
    get_cities_keyboard, 
    get_route_points_keyboard,
    get_confirmation_keyboard,
    get_complete_route_keyboard,
    get_photo_actions_keyboard,
    get_finish_photos_keyboard
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
        collected_containers={}
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
    
    # Начинаем с первой точки маршрута
    current_point = route_points[0]
    
    # Обновляем данные состояния
    await state.update_data(
        current_point=current_point,
        total_points=len(route_points)
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
        collected_containers={}
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
    
    # Переводим в состояние выбора действия с фотографией
    await state.set_state(RouteStates.waiting_for_photo_decision)
    
    await message.answer(
        f"📸 Фотография получена! ({len(photos_list)} из любого количества)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"Что делаем дальше?",
        reply_markup=get_photo_actions_keyboard()
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
    """
    state_data = await state.get_data()
    current_point = state_data.get('current_point')
    photos_list = state_data.get('photos_list', [])
    
    # Переводим в состояние ожидания количества контейнеров
    await state.set_state(RouteStates.waiting_for_containers_count)
    
    await callback.message.edit_text(
        f"📸 Все фотографии сохранены! ({len(photos_list)} шт.)\n\n"
        f"📍 Точка: <b>{current_point['name']}</b>\n"
        f"🏢 Организация: <b>{current_point['organization']}</b>\n\n"
        f"📦 Укажите количество собранных контейнеров\n"
        f"Введите число от {MIN_CONTAINERS} до {MAX_CONTAINERS}:"
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
    
    # Сохраняем количество контейнеров в состоянии и переходим к комментарию
    await state.update_data(containers_count=containers_count)
    await state.set_state(RouteStates.waiting_for_comment)
    
    await message.answer(
        f"✅ Количество контейнеров: {containers_count}\n\n"
        f"📝 Напишите короткий комментарий к этой точке маршрута:"
    )


@user_router.message(F.text, RouteStates.waiting_for_comment)
async def comment_received(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Обработчик получения комментария к точке маршрута.
    
    Сохраняет всю информацию о точке в базу данных и переходит к следующей точке.
    
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
    selected_city = state_data.get('selected_city')
    current_point_index = state_data.get('current_point_index', 0)
    total_points = state_data.get('total_points', 0)
    collected_containers = state_data.get('collected_containers', {})
    containers_count = state_data.get('containers_count', 0)
    
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
            user_id=message.from_user.id,
            route_id=route_record.id,
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
    await state.update_data(collected_containers=collected_containers)
    
    # Проверяем, есть ли ещё точки в маршруте
    next_point_index = current_point_index + 1
    
    if next_point_index < total_points:
        # Переходим к следующей точке
        route_points = AVAILABLE_ROUTES[selected_city]
        next_point = route_points[next_point_index]
        
        await state.update_data(
            current_point=next_point,
            current_point_index=next_point_index,
            photos_list=[]  # Очищаем список фотографий для новой точки
        )
        
        # Переводим в состояние ожидания фото для следующей точки
        await state.set_state(RouteStates.waiting_for_photo)
        
        point_info = format_route_progress(
            city=selected_city,
            current_point=next_point,
            total_points=total_points,
            current_index=next_point_index,
            collected_containers=collected_containers
        )
        point_info = f"✅ Точка завершена! Собрано контейнеров: {containers_count}, фото: {len(photos_list)}\n💬 Комментарий: {comment}\n\n{point_info}\n\n📸 Сделайте фотографию в данной точке"
        
        await message.answer(point_info)
        
    else:
        # Все точки пройдены, переходим к завершению маршрута
        await state.set_state(RouteStates.waiting_for_route_completion)
        
        # Формируем сводку по маршруту
        summary = f"🎉 <b>Все точки маршрута пройдены!</b>\n\n"
        summary += f"📊 <b>Сводка по сбору:</b>\n"
        
        total_collected = 0
        for organization, count in collected_containers.items():
            summary += f"• {organization}: {count} контейнеров\n"
            total_collected += count
        
        summary += f"\n📦 <b>Всего собрано:</b> {total_collected} контейнеров"
        
        await message.answer(
            text=summary,
            reply_markup=get_complete_route_keyboard()
        )


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
    Показывает историю маршрутов пользователя.
    
    Args:
        message: Объект сообщения от пользователя
    """
    async for session in get_session():
        # Получаем все маршруты пользователя с детализацией
        stmt = select(RouteProgress).options(
            selectinload(RouteProgress.route)
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
        
        # Группируем маршруты по дате и городу
        routes_summary = {}
        for route_progress in routes_list:
            date = route_progress.visited_at.strftime("%d.%m.%Y")
            city = route_progress.route.city_name
            
            key = f"{date} - {city}"
            if key not in routes_summary:
                routes_summary[key] = []
            
            routes_summary[key].append(route_progress)
        
        # Формируем ответное сообщение
        response = "📊 <b>История ваших маршрутов:</b>\n\n"
        
        for route_key, progresses in list(routes_summary.items())[:10]:  # Последние 10
            response += f"📅 <b>{route_key}</b>\n"
            
            total_containers = sum(p.containers_count for p in progresses)
            organizations = set(p.route.organization for p in progresses)
            
            response += f"📦 Собрано контейнеров: {total_containers}\n"
            response += f"🏢 Организации: {', '.join(organizations)}\n"
            response += f"📍 Точек пройдено: {len(progresses)}\n\n"
        
        await message.answer(
            text=response,
            reply_markup=get_main_menu_keyboard()
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
    else:
        await message.answer(
            "🤔 Я не понимаю это сообщение. Используйте кнопки меню или команды.",
            reply_markup=get_main_menu_keyboard()
        )
