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
from utils.callback_manager import (
    create_route_callback, create_route_point_callback, create_photo_callback,
    create_lab_data_callback, create_specific_lab_callback, create_lab_photo_callback,
    create_lab_comment_callback, create_back_to_route_callback
)


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
        # Новые кнопки для обработки/пропуска точки
        builder.add(
            InlineKeyboardButton(
                text="📸 Обработать точку",
                callback_data=f"process_point:{current_point_index}"
            ),
            InlineKeyboardButton(
                text="⏭️ Пропустить точку",
                callback_data=f"skip_point:{current_point_index}"
            )
        )
    
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
    Создаёт клавиатуру для перехода к заполнению итогов по лабораториям.
    
    Показывается после прохождения всех точек маршрута.
    Теперь вместо завершения сразу переходим к заполнению данных по лабораториям.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для перехода к лабораториям
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="📋 Заполнить данные по лабораториям",
            callback_data="start_lab_summaries"
        )
    )
    
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
    containers_count: int = None,
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
        containers_text = f"📦 Контейнеры ({containers_count if containers_count is not None else 0} шт.) ✅"
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


def get_point_action_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора действия с точкой маршрута.
    
    Returns:
        InlineKeyboardMarkup с кнопками обработки и пропуска
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="📸 Обработать точку",
            callback_data="process_point"
        ),
        InlineKeyboardButton(
            text="⏭️ Пропустить точку",
            callback_data="skip_point"
        )
    )
    
    # Кнопка отмены маршрута
    builder.add(InlineKeyboardButton(
        text="❌ Отменить маршрут",
        callback_data="confirm_cancel_route"
    ))
    
    # Кнопки в одном ряду, отмена отдельно
    builder.adjust(2, 1)
    
    return builder.as_markup()


def get_route_selection_keyboard(routes_data: list, has_more: bool = False, offset: int = 0) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора маршрута из истории.
    
    Args:
        routes_data: Список словарей с данными маршрутов
        has_more: Есть ли еще маршруты для загрузки
        offset: Текущий сдвиг для пагинации
    
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
        callback_data = create_route_callback(route_data['route_id'])
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=callback_data
        ))
    
    # Кнопка "Показать еще" если есть больше маршрутов
    if has_more:
        builder.add(InlineKeyboardButton(
            text="📋 Показать еще",
            callback_data=f"load_more_routes:{offset + len(routes_data)}"
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
    has_photos: bool = False,
    has_lab_data: bool = False
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для детального просмотра маршрута.
    
    Args:
        route_id: ID маршрута
        current_point_index: Индекс текущей точки (0-based)
        total_points: Общее количество точек
        has_photos: Есть ли фотографии у текущей точки
        has_lab_data: Есть ли итоговые данные по лабораториям
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации по точкам
    if current_point_index > 0:
        builder.add(InlineKeyboardButton(
            text="⬅️ Предыдущая точка",
            callback_data=create_route_point_callback(route_id, current_point_index - 1)
        ))
    
    if current_point_index < total_points - 1:
        builder.add(InlineKeyboardButton(
            text="Следующая точка ➡️",
            callback_data=create_route_point_callback(route_id, current_point_index + 1)
        ))
    
    # Кнопка просмотра фотографий (если есть)
    if has_photos:
        builder.add(InlineKeyboardButton(
            text="📸 Просмотреть фотографии",
            callback_data=create_photo_callback(route_id, current_point_index, 0)
        ))
    
    # Кнопка просмотра данных лабораторий (если есть)
    if has_lab_data:
        builder.add(InlineKeyboardButton(
            text="🏥 Данные лабораторий",
            callback_data=create_lab_data_callback(route_id)
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
    # Подсчитываем количество специальных кнопок (фото + лаборатории)
    special_buttons_count = int(has_photos) + int(has_lab_data)
    
    if current_point_index > 0 and current_point_index < total_points - 1:
        # Навигация в одном ряду, остальные отдельно
        if special_buttons_count > 0:
            builder.adjust(2, *([1] * special_buttons_count), 1, 1)
        else:
            builder.adjust(2, 1, 1)
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
            callback_data=create_photo_callback(route_id, point_index, current_photo_index - 1)
        ))
    
    if current_photo_index < total_photos - 1:
        builder.add(InlineKeyboardButton(
            text="Следующее фото ➡️",
            callback_data=create_photo_callback(route_id, point_index, current_photo_index + 1)
        ))
    
    # Информация о текущей фотографии
    builder.add(InlineKeyboardButton(
        text=f"📸 {current_photo_index + 1} из {total_photos}",
        callback_data="photo_info"
    ))
    
    # Кнопка возврата к деталям маршрута
    builder.add(InlineKeyboardButton(
        text="🔙 К деталям маршрута",
        callback_data=create_route_point_callback(route_id, point_index)
    ))
    
    # Размещаем кнопки
    if current_photo_index > 0 and current_photo_index < total_photos - 1:
        builder.adjust(2, 1, 1)  # Навигация в одном ряду
    else:
        builder.adjust(1)  # Все кнопки отдельно
    
    return builder.as_markup()


def get_lab_selection_keyboard(labs_data: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора лаборатории для заполнения итоговых данных.
    
    Args:
        labs_data: Список словарей с данными лабораторий
        Формат: [{'organization': 'КДЛ', 'is_completed': False, 'points_count': 2}, ...]
    
    Returns:
        InlineKeyboardMarkup с кнопками выбора лабораторий
    """
    builder = InlineKeyboardBuilder()
    
    for lab_data in labs_data:
        organization = lab_data['organization']
        is_completed = lab_data.get('is_completed', False)
        points_count = lab_data.get('points_count', 0)
        
        # Формируем текст кнопки с индикатором статуса
        status_emoji = "✅" if is_completed else "⏳"
        button_text = f"{status_emoji} {organization} ({points_count} точек)"
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"select_lab:{organization}"
        ))
    
    # Кнопка завершения всех лабораторий (доступна только если все заполнены)
    all_completed = all(lab['is_completed'] for lab in labs_data)
    if all_completed:
        builder.add(InlineKeyboardButton(
            text="🏁 Завершить маршрут",
            callback_data="complete_route_final"
        ))
    
    # Размещаем кнопки по одной в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_lab_summary_management_keyboard(
    has_photos: bool = False,
    has_comment: bool = False,
    photos_count: int = 0,
    comment_text: str = "",
    organization: str = ""
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для управления итоговыми данными лаборатории.
    
    Args:
        has_photos: Есть ли итоговые фотографии
        has_comment: Есть ли итоговый комментарий
        photos_count: Количество фотографий
        comment_text: Текст комментария (для превью)
        organization: Название организации
    
    Returns:
        InlineKeyboardMarkup с кнопками управления данными лаборатории
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка для фотографий
    if has_photos:
        photo_text = f"📸 Фото ({photos_count} шт.) ✅"
        photo_callback = "edit_lab_photos"
    else:
        photo_text = "📸 Добавить фотографии лаборатории"
        photo_callback = "add_lab_photos"
    
    builder.add(InlineKeyboardButton(text=photo_text, callback_data=photo_callback))
    
    # Кнопка для комментария
    if has_comment:
        comment_preview = comment_text[:20] + "..." if len(comment_text) > 20 else comment_text
        comment_text_btn = f"📝 Комментарий ({comment_preview}) ✅"
        comment_callback = "edit_lab_comment"
    else:
        comment_text_btn = "📝 Добавить комментарий (необязательно)"
        comment_callback = "add_lab_comment"
    
    builder.add(InlineKeyboardButton(text=comment_text_btn, callback_data=comment_callback))
    
    # Кнопка "Завершить" - показывается только если есть хотя бы одно фото
    if has_photos:
        builder.add(InlineKeyboardButton(
            text="✅ Завершить данную лабораторию", 
            callback_data=f"complete_lab:{organization}"
        ))
    
    # Кнопка возврата к списку лабораторий
    builder.add(InlineKeyboardButton(
        text="🔙 К списку лабораторий",
        callback_data="back_to_lab_selection"
    ))
    
    # Размещаем все кнопки по одной в ряду
    builder.adjust(1)
    
    return builder.as_markup()


def get_lab_photos_keyboard(photos_count: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для управления фотографиями лаборатории.
    
    Args:
        photos_count: Количество уже добавленных фотографий
    
    Returns:
        InlineKeyboardMarkup с кнопками управления фотографиями
    """
    builder = InlineKeyboardBuilder()
    
    if photos_count > 0:
        builder.add(
            InlineKeyboardButton(
                text=f"✅ Готово ({photos_count} фото)",
                callback_data="finish_lab_photos"
            ),
            InlineKeyboardButton(
                text="📸 Добавить еще",
                callback_data="add_more_lab_photos"
            )
        )
        
        # Если фото больше 1, можно удалить последнее
        if photos_count > 1:
            builder.add(InlineKeyboardButton(
                text="🗑 Удалить последнее фото",
                callback_data="remove_last_lab_photo"
            ))
        
        builder.adjust(2, 1)
    else:
        builder.add(InlineKeyboardButton(
            text="📸 Добавить первое фото",
            callback_data="add_first_lab_photo"
        ))
    
    return builder.as_markup()


def get_lab_comment_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подтверждения сохранения комментария.
    
    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="✅ Сохранить комментарий",
            callback_data="save_lab_comment"
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_lab_comment"
        )
    )
    
    builder.adjust(2)
    
    return builder.as_markup()


def get_route_lab_data_keyboard(route_id: str, labs_data: list) -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра списка лабораторий в рамках маршрута.
    
    Args:
        route_id: ID маршрута
        labs_data: Список словарей с данными лабораторий
    
    Returns:
        InlineKeyboardMarkup с кнопками лабораторий
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждой лаборатории
    for lab in labs_data:
        organization = lab['organization']
        photos_count = lab['photos_count']
        has_comment = lab['has_comment']
        
        # Иконки статуса
        photo_icon = f"📸{photos_count}" if photos_count > 0 else "📸➖"
        comment_icon = "📝✅" if has_comment else "📝➖"
        
        button_text = f"🏥 {organization} ({photo_icon} {comment_icon})"
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=create_specific_lab_callback(route_id, organization)
        ))
    
    # Кнопка возврата
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад к маршруту",
        callback_data=create_back_to_route_callback(route_id, 0)
    ))
    
    # Размещаем кнопки: лаборатории по одной, кнопка назад отдельно
    builder.adjust(1)
    
    return builder.as_markup()


def get_lab_data_viewer_keyboard(
    route_id: str, 
    organization: str, 
    current_photo_index: int, 
    total_photos: int,
    has_comment: bool
) -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра данных конкретной лаборатории.
    
    Args:
        route_id: ID маршрута
        organization: Название лаборатории
        current_photo_index: Индекс текущей фотографии
        total_photos: Общее количество фотографий
        has_comment: Наличие комментария
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    builder = InlineKeyboardBuilder()
    
    # Навигация по фотографиям (если есть несколько)
    if total_photos > 1:
        if current_photo_index > 0:
            builder.add(InlineKeyboardButton(
                text="⬅️ Предыдущая",
                callback_data=create_lab_photo_callback(route_id, organization, current_photo_index - 1)
            ))
        
        if current_photo_index < total_photos - 1:
            builder.add(InlineKeyboardButton(
                text="Следующая ➡️",
                callback_data=create_lab_photo_callback(route_id, organization, current_photo_index + 1)
            ))
    
    # Кнопка просмотра комментария (если есть)
    if has_comment:
        builder.add(InlineKeyboardButton(
            text="📝 Показать комментарий",
            callback_data=create_lab_comment_callback(route_id, organization)
        ))
    
    # Кнопка возврата к списку лабораторий
    builder.add(InlineKeyboardButton(
        text="⬅️ К списку лабораторий",
        callback_data=create_lab_data_callback(route_id)
    ))
    
    # Размещаем кнопки
    if total_photos > 1:
        # Навигация в одном ряду, остальные отдельно
        nav_buttons = 0
        if current_photo_index > 0:
            nav_buttons += 1
        if current_photo_index < total_photos - 1:
            nav_buttons += 1
        
        if nav_buttons == 2:
            builder.adjust(2, 1, 1)  # Навигация в одном ряду
        else:
            builder.adjust(1)  # Все кнопки отдельно
    else:
        builder.adjust(1)
    
    return builder.as_markup()
