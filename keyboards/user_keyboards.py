"""
Клавиатуры и кнопки для пользователей курьерского бота.

Этот модуль содержит функции для создания различных типов клавиатур:
- Reply клавиатуры (отображаются вместо стандартной клавиатуры)
- Inline клавиатуры (прикрепляются к сообщениям)

Все клавиатуры создаются динамически с использованием билдеров aiogram 3.x
для лучшей гибкости и поддержки различных размеров экрана.
"""

from typing import List, Optional
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from config import AVAILABLE_ROUTES


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Создаёт главную клавиатуру меню бота.
    
    Эта клавиатура содержит основные действия, доступные пользователю:
    - Выбор нового маршрута
    - Просмотр истории маршрутов
    - Помощь
    
    Returns:
        ReplyKeyboardMarkup: Готовая клавиатура главного меню
    """
    # Используем ReplyKeyboardBuilder для удобного создания клавиатуры
    builder = ReplyKeyboardBuilder()
    
    # Добавляем основные кнопки
    builder.add(KeyboardButton(text="🚚 Выбрать маршрут"))
    builder.add(KeyboardButton(text="📊 Мои маршруты"))
    builder.add(KeyboardButton(text="❓ Помощь"))
    builder.add(KeyboardButton(text="ℹ️ О боте"))
    
    # Настраиваем расположение кнопок: 2 кнопки в первом ряду, 2 во втором
    builder.adjust(2, 2)
    
    return builder.as_markup(
        resize_keyboard=True,  # Автоматически подгоняет размер под экран
        one_time_keyboard=False,  # Клавиатура остаётся видимой
        input_field_placeholder="Выберите действие..."  # Подсказка в поле ввода
    )


def get_cities_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт inline клавиатуру для выбора городов маршрута.
    
    Динамически генерирует кнопки на основе доступных маршрутов
    из конфигурации AVAILABLE_ROUTES.
    
    Returns:
        InlineKeyboardMarkup: Inline клавиатура с городами
    """
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопку для каждого города из конфигурации
    for city_name in AVAILABLE_ROUTES.keys():
        # Подсчитываем количество точек в маршруте
        points_count = len(AVAILABLE_ROUTES[city_name])
        
        # Создаём текст кнопки с информацией о количестве точек
        button_text = f"{city_name} ({points_count} точек)"
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"city:{city_name}"
        ))
    
    # Добавляем кнопку отмены
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_city_selection"
    ))
    
    # Размещаем кнопки по одной в ряду для лучшей читаемости
    builder.adjust(1)
    
    return builder.as_markup()


def get_route_points_keyboard(city_name: str, current_point_index: int = 0) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для отображения точек маршрута.
    
    Показывает прогресс прохождения маршрута и доступные действия.
    
    Args:
        city_name: Название города
        current_point_index: Индекс текущей точки маршрута
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с точками маршрута
    """
    if city_name not in AVAILABLE_ROUTES:
        # Возвращаем пустую клавиатуру если город не найден
        return InlineKeyboardBuilder().as_markup()
    
    builder = InlineKeyboardBuilder()
    route_points = AVAILABLE_ROUTES[city_name]
    
    # Создаём кнопки для каждой точки маршрута
    for index, point in enumerate(route_points):
        # Определяем статус точки
        if index < current_point_index:
            status_emoji = "✅"  # Завершена
        elif index == current_point_index:
            status_emoji = "📍"  # Текущая
        else:
            status_emoji = "⏳"  # Ожидает
        
        button_text = f"{status_emoji} {point['organization']} - {point['name']}"
        
        # Кнопки точек не активны, служат только для отображения
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"point_info:{index}"
        ))
    
    # Добавляем функциональные кнопки в зависимости от прогресса
    if current_point_index < len(route_points):
        builder.add(InlineKeyboardButton(
            text="📸 Загрузить фото",
            callback_data=f"upload_photo:{current_point_index}"
        ))
    
    # Кнопка завершения маршрута (доступна когда все точки пройдены)
    if current_point_index >= len(route_points):
        builder.add(InlineKeyboardButton(
            text="🏁 Завершить маршрут",
            callback_data="complete_route"
        ))
    
    # Кнопка отмены маршрута
    builder.add(InlineKeyboardButton(
        text="❌ Отменить маршрут",
        callback_data="cancel_route"
    ))
    
    # Размещаем кнопки: точки по одной в ряду, функциональные кнопки в конце
    points_count = len(route_points)
    adjust_args = [1] * points_count + [2]  # например [1,1,1,2]
    builder.adjust(*adjust_args)
    
    return builder.as_markup()


def get_confirmation_keyboard(confirm_text: str = "✅ Да", 
                            cancel_text: str = "❌ Нет",
                            confirm_callback: str = "confirm",
                            cancel_callback: str = "cancel") -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру подтверждения действия.
    
    Универсальная функция для создания клавиатур подтверждения
    с настраиваемыми текстами и callback_data.
    
    Args:
        confirm_text: Текст кнопки подтверждения
        cancel_text: Текст кнопки отмены
        confirm_callback: Callback data для подтверждения
        cancel_callback: Callback data для отмены
        
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
        InlineKeyboardButton(text=cancel_text, callback_data=cancel_callback)
    )
    
    # Размещаем кнопки в одном ряду
    builder.adjust(2)
    
    return builder.as_markup()


def get_complete_route_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для завершения маршрута.
    
    Показывается после прохождения всех точек маршрута
    и предлагает завершить маршрут или вернуться к редактированию.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура завершения маршрута
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="🏁 Завершить маршрут",
            callback_data="complete_route"
        ),
        InlineKeyboardButton(
            text="📝 Добавить комментарий",
            callback_data="add_route_comment"
        ),
        InlineKeyboardButton(
            text="❌ Отменить маршрут",
            callback_data="cancel_route"
        )
    )
    
    # Размещаем кнопки: первая отдельно, остальные в одном ряду
    builder.adjust(1, 2)
    
    return builder.as_markup()


def get_organizations_keyboard(organizations: List[str]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для выбора организации.
    
    Используется при формировании доставок или фильтрации данных.
    
    Args:
        organizations: Список названий организаций
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с организациями
    """
    builder = InlineKeyboardBuilder()
    
    for org in organizations:
        builder.add(InlineKeyboardButton(
            text=f"🏢 {org}",
            callback_data=f"org:{org}"
        ))
    
    # Кнопка для выбора всех организаций
    builder.add(InlineKeyboardButton(
        text="📋 Все организации",
        callback_data="org:all"
    ))
    
    # Размещаем по одной организации в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_boxes_input_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для быстрого ввода количества коробок.
    
    Предлагает часто используемые значения для ускорения ввода.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с числами
    """
    builder = InlineKeyboardBuilder()
    
    # Часто используемые значения
    common_values = [1, 2, 3, 5, 10, 15, 20, 25]
    
    for value in common_values:
        builder.add(InlineKeyboardButton(
            text=str(value),
            callback_data=f"boxes:{value}"
        ))
    
    # Кнопка для ручного ввода
    builder.add(InlineKeyboardButton(
        text="✍️ Ввести другое число",
        callback_data="boxes:manual"
    ))
    
    # Размещаем числа по 4 в ряду
    builder.adjust(4, 4, 1)
    
    return builder.as_markup()


def get_navigation_keyboard(has_prev: bool = False, has_next: bool = False) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру навигации для пагинации.
    
    Args:
        has_prev: Есть ли предыдущая страница
        has_next: Есть ли следующая страница
        
    Returns:
        InlineKeyboardMarkup: Клавиатура навигации
    """
    builder = InlineKeyboardBuilder()
    
    if has_prev:
        builder.add(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="nav:prev"
        ))
    
    if has_next:
        builder.add(InlineKeyboardButton(
            text="Вперёд ➡️",
            callback_data="nav:next"
        ))
    
    # Кнопка возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🏠 В главное меню",
        callback_data="nav:main"
    ))
    
    # Размещение зависит от количества кнопок
    if has_prev and has_next:
        builder.adjust(2, 1)  # Навигация в одном ряду, меню отдельно
    else:
        builder.adjust(1)  # Все кнопки отдельно
    
    return builder.as_markup()


def get_photo_actions_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для действий с фотографией.
    
    Показывается после получения первой фотографии с точки маршрута.
    
    Returns:
        InlineKeyboardMarkup с кнопками добавления фото и продолжения
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="📸 Добавить еще фото",
            callback_data="add_more_photos"
        ),
        InlineKeyboardButton(
            text="📦 Указать количество контейнеров",
            callback_data="proceed_to_boxes"
        )
    )
    
    # Размещаем кнопки по одной в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_finish_photos_keyboard(photos_count: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для завершения добавления фотографий.
    
    Args:
        photos_count: Количество уже добавленных фотографий
    
    Returns:
        InlineKeyboardMarkup с кнопками завершения и добавления
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text=f"✅ Готово ({photos_count} фото)",
            callback_data="finish_photos"
        ),
        InlineKeyboardButton(
            text="📸 Добавить еще",
            callback_data="add_one_more_photo"
        )
    )
    
    # Размещаем кнопки по одной в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_point_data_management_keyboard(
    has_photos: bool = False, 
    has_containers: bool = False, 
    has_comment: bool = False,
    photos_count: int = 0,
    containers_count: int = 0,
    comment_text: str = ""
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для управления данными точки маршрута.
    
    Позволяет добавлять/редактировать фото, контейнеры и комментарий.
    Показывает кнопку "Продолжить маршрут" только когда все данные заполнены.
    
    Args:
        has_photos: Есть ли фотографии
        has_containers: Указано ли количество контейнеров
        has_comment: Добавлен ли комментарий
        photos_count: Количество фотографий
        containers_count: Количество контейнеров
        comment_text: Текст комментария (для превью)
    
    Returns:
        InlineKeyboardMarkup с кнопками управления данными
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка для фотографий
    if has_photos:
        photo_text = f"📸 Фото ({photos_count} шт.) ✅"
        photo_callback = "edit_photos"
    else:
        photo_text = "📸 Добавить фото"
        photo_callback = "add_photos"
    
    builder.add(InlineKeyboardButton(text=photo_text, callback_data=photo_callback))
    
    # Кнопка для контейнеров
    if has_containers:
        containers_text = f"📦 Контейнеры ({containers_count} шт.) ✅"
        containers_callback = "edit_containers"
    else:
        containers_text = "📦 Указать количество контейнеров"
        containers_callback = "add_containers"
    
    builder.add(InlineKeyboardButton(text=containers_text, callback_data=containers_callback))
    
    # Кнопка для комментария  
    if has_comment:
        comment_preview = comment_text[:20] + "..." if len(comment_text) > 20 else comment_text
        comment_text = f"📝 Комментарий ({comment_preview}) ✅"
        comment_callback = "edit_comment"
    else:
        comment_text = "📝 Добавить комментарий"
        comment_callback = "add_comment"
    
    builder.add(InlineKeyboardButton(text=comment_text, callback_data=comment_callback))
    
    # Кнопка "Продолжить маршрут" - показывается только если все данные заполнены
    # has_containers может быть True даже при 0 контейнерах
    if has_photos and has_containers and has_comment:
        builder.add(InlineKeyboardButton(
            text="🚀 Продолжить маршрут", 
            callback_data="continue_route"
        ))
    
    # Размещаем все кнопки по одной в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_route_selection_keyboard(routes_data: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора маршрута из истории.
    
    Args:
        routes_data: Список словарей с данными маршрутов
    
    Returns:
        InlineKeyboardMarkup с кнопками выбора маршрутов
    """
    builder = InlineKeyboardBuilder()
    
    for i, route_data in enumerate(routes_data):
        # Формируем текст кнопки: дата - город - количество точек
        date = route_data['date']
        city = route_data['city']
        points_count = route_data['points_count']
        total_containers = route_data['total_containers']
        
        button_text = f"📅 {date} - {city} ({points_count} точек, {total_containers} контейнеров)"
        callback_data = f"view_route:{route_data['route_id']}"
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=callback_data
        ))
    
    # Кнопка возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🔙 Назад в меню",
        callback_data="back_to_main_menu"
    ))
    
    # Размещаем кнопки по одной в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_route_detail_keyboard(
    route_id: str,
    current_point_index: int,
    total_points: int,
    has_photos: bool = False
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для детального просмотра маршрута.
    
    Args:
        route_id: ID маршрута
        current_point_index: Индекс текущей точки (0-based)
        total_points: Общее количество точек
        has_photos: Есть ли фотографии у текущей точки
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации по точкам
    if current_point_index > 0:
        builder.add(InlineKeyboardButton(
            text="⬅️ Предыдущая точка",
            callback_data=f"route_point:{route_id}:{current_point_index - 1}"
        ))
    
    if current_point_index < total_points - 1:
        builder.add(InlineKeyboardButton(
            text="Следующая точка ➡️",
            callback_data=f"route_point:{route_id}:{current_point_index + 1}"
        ))
    
    # Кнопка просмотра фотографий (если есть)
    if has_photos:
        builder.add(InlineKeyboardButton(
            text="📸 Просмотреть фотографии",
            callback_data=f"view_photos:{route_id}:{current_point_index}"
        ))
    
    # Кнопка возврата к списку маршрутов
    builder.add(InlineKeyboardButton(
        text="📋 К списку маршрутов",
        callback_data="back_to_routes"
    ))
    
    # Кнопка возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🔙 Главное меню",
        callback_data="back_to_main_menu"
    ))
    
    # Размещаем кнопки
    if current_point_index > 0 and current_point_index < total_points - 1:
        builder.adjust(2, 1, 1, 1)  # Навигация в одном ряду, остальные отдельно
    else:
        builder.adjust(1)  # Все кнопки отдельно
    
    return builder.as_markup()


def get_photos_viewer_keyboard(
    route_id: str,
    point_index: int,
    current_photo_index: int,
    total_photos: int
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для просмотра фотографий точки маршрута.
    
    Args:
        route_id: ID маршрута
        point_index: Индекс точки
        current_photo_index: Индекс текущей фотографии (0-based)
        total_photos: Общее количество фотографий
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации по фотографиям
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации по фотографиям
    if current_photo_index > 0:
        builder.add(InlineKeyboardButton(
            text="⬅️ Предыдущее фото",
            callback_data=f"view_photo:{route_id}:{point_index}:{current_photo_index - 1}"
        ))
    
    if current_photo_index < total_photos - 1:
        builder.add(InlineKeyboardButton(
            text="Следующее фото ➡️",
            callback_data=f"view_photo:{route_id}:{point_index}:{current_photo_index + 1}"
        ))
    
    # Информация о текущей фотографии
    builder.add(InlineKeyboardButton(
        text=f"📸 {current_photo_index + 1} из {total_photos}",
        callback_data="photo_info"
    ))
    
    # Кнопка возврата к деталям маршрута
    builder.add(InlineKeyboardButton(
        text="🔙 К деталям маршрута",
        callback_data=f"route_point:{route_id}:{point_index}"
    ))
    
    # Размещаем кнопки
    if current_photo_index > 0 and current_photo_index < total_photos - 1:
        builder.adjust(2, 1, 1)  # Навигация в одном ряду
    else:
        builder.adjust(1)  # Все кнопки отдельно
    
    return builder.as_markup()
