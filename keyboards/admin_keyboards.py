"""
Клавиатуры для административных функций бота.

Этот модуль содержит функции для создания клавиатур,
используемых в административном интерфейсе бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from typing import List, Optional


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает основное меню администратора.
    
    Returns:
        ReplyKeyboardMarkup с кнопками админ-меню
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="📋 Активные доставки")
            ],
            [
                KeyboardButton(text="🏢 Склад Ярославль"),
                KeyboardButton(text="📥 Экспорт отчетов")
            ],
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="🏠 Главное меню")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_statistics_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для меню статистики.
    
    Returns:
        InlineKeyboardMarkup с кнопками статистики
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📈 Общая статистика",
                    callback_data="stats_general"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Статистика курьеров",
                    callback_data="stats_couriers"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛣️ Мониторинг маршрутов",
                    callback_data="stats_routes_monitoring"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 За сегодня",
                    callback_data="stats_today"
                ),
                InlineKeyboardButton(
                    text="📅 За неделю",
                    callback_data="stats_week"
                ),
                InlineKeyboardButton(
                    text="📅 За месяц",
                    callback_data="stats_month"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="stats_refresh"
                ),
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="stats_close"
                )
            ]
        ]
    )
    return keyboard


def get_export_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для меню экспорта отчетов.
    
    Returns:
        InlineKeyboardMarkup с кнопками экспорта
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Excel отчет",
                    callback_data="export_excel"
                ),
                InlineKeyboardButton(
                    text="📄 PDF отчет",
                    callback_data="export_pdf"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Выбрать период",
                    callback_data="export_select_period"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="export_close"
                )
            ]
        ]
    )
    return keyboard


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для меню настроек.
    
    Returns:
        InlineKeyboardMarkup с кнопками настроек
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Управление курьерами",
                    callback_data="settings_couriers"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛣 Управление маршрутами",
                    callback_data="settings_routes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Резервное копирование",
                    callback_data="settings_backup"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="settings_close"
                )
            ]
        ]
    )
    return keyboard


def get_period_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора периода отчета.
    
    Returns:
        InlineKeyboardMarkup с кнопками выбора периода
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Сегодня",
                    callback_data="period_today"
                ),
                InlineKeyboardButton(
                    text="📅 Вчера",
                    callback_data="period_yesterday"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Неделя",
                    callback_data="period_week"
                ),
                InlineKeyboardButton(
                    text="📅 Месяц",
                    callback_data="period_month"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Выбрать даты",
                    callback_data="period_custom"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="period_cancel"
                )
            ]
        ]
    )
    return keyboard


def get_warehouse_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для управления складом.
    
    Returns:
        InlineKeyboardMarkup с кнопками управления складом
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Текущее состояние",
                    callback_data="warehouse_status"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚚 Сформировать маршрут в Москву",
                    callback_data="warehouse_create_moscow_route"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📈 За сегодня",
                    callback_data="warehouse_today"
                ),
                InlineKeyboardButton(
                    text="📈 За неделю",
                    callback_data="warehouse_week"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📈 За месяц",
                    callback_data="warehouse_month"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="warehouse_refresh"
                ),
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="warehouse_close"
                )
            ]
        ]
    )
    return keyboard


def get_routes_monitoring_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для мониторинга маршрутов.
    
    Returns:
        InlineKeyboardMarkup с кнопками мониторинга маршрутов
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏃‍♂️ Активные маршруты",
                    callback_data="routes_active"
                ),
                InlineKeyboardButton(
                    text="✅ Завершенные маршруты",
                    callback_data="routes_completed"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📍 Маршруты по городам",
                    callback_data="routes_by_cities"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚚 Маршруты в Москву",
                    callback_data="routes_moscow"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Сводка",
                    callback_data="routes_summary"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="routes_refresh"
                ),
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="routes_close"
                )
            ]
        ]
    )
    return keyboard


def get_route_details_keyboard(route_session_id: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для детального просмотра маршрута.
    
    Args:
        route_session_id: ID сессии маршрута
        
    Returns:
        InlineKeyboardMarkup с кнопками для работы с маршрутом
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Просмотреть фото",
                    callback_data=f"route_photos:{route_session_id}"
                ),
                InlineKeyboardButton(
                    text="💬 Комментарии",
                    callback_data=f"route_comments:{route_session_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Детальная информация",
                    callback_data=f"route_details:{route_session_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к списку",
                    callback_data="routes_back_to_list"
                )
            ]
        ]
    )
    return keyboard


def get_city_selection_keyboard(cities: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора города.
    
    Args:
        cities: Список городов
        
    Returns:
        InlineKeyboardMarkup с кнопками городов
    """
    buttons = []
    for city in cities:
        buttons.append([
            InlineKeyboardButton(
                text=f"📍 {city}",
                callback_data=f"city_routes:{city}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="routes_monitoring_back"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


# Временное хранилище для сопоставления хешей с полными route_id
_route_hash_map = {}

def get_admin_route_selection_keyboard(routes_data: list, has_more: bool = False, offset: int = 0) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора маршрута из списка (для админа).
    
    Args:
        routes_data: Список словарей с данными маршрутов
        has_more: Есть ли еще маршруты для загрузки
        offset: Текущий сдвиг для пагинации
    
    Returns:
        InlineKeyboardMarkup с кнопками выбора маршрутов
    """
    keyboard_rows = []
    
    for i, route_data in enumerate(routes_data):
        # Формируем текст кнопки: дата - город - курьер - количество точек
        date = route_data.get('date', 'Неизвестно')
        city = route_data.get('city', 'Неизвестно')
        username = route_data.get('username', 'Неизвестно')
        points_count = route_data.get('points_count', 0)
        total_containers = route_data.get('total_containers', 0)
        status = route_data.get('status', 'unknown')
        
        # Эмодзи статуса
        status_emoji = {
            'active': '🟢',
            'paused': '🟡', 
            'completed': '✅',
            'inactive': '⚪'
        }.get(status, '❓')
        
        button_text = f"{status_emoji} {date} {city} - {username} ({points_count}т, {total_containers}к)"
        
        # Используем хеш от route_id для коротких callback_data
        import hashlib
        route_hash = hashlib.md5(route_data['route_id'].encode()).hexdigest()[:8]
        callback_data = f"admin_route:{route_hash}"
        
        # Сохраняем соответствие хеша и полного route_id
        _route_hash_map[route_hash] = route_data['route_id']
        
        keyboard_rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=callback_data
            )
        ])
    
    # Кнопка "Показать еще" если есть больше маршрутов
    if has_more:
        keyboard_rows.append([
            InlineKeyboardButton(
                text="📋 Показать еще",
                callback_data=f"admin_load_more_routes:{offset + len(routes_data)}"
            )
        ])
    
    # Кнопка возврата в меню мониторинга
    keyboard_rows.append([
        InlineKeyboardButton(
            text="⬅️ Назад к мониторингу",
            callback_data="routes_monitoring_back"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_admin_route_detail_keyboard(
    route_id: str,
    current_point_index: int,
    total_points: int,
    has_photos: bool = False,
    has_lab_data: bool = False
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для детального просмотра маршрута (для админа).
    
    Args:
        route_id: ID маршрута (route_session_id)
        current_point_index: Индекс текущей точки (0-based)
        total_points: Общее количество точек
        has_photos: Есть ли фотографии у текущей точки
        has_lab_data: Есть ли итоговые данные по лабораториям
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    keyboard_rows = []
    
    # Кнопки навигации по точкам
    nav_buttons = []
    if current_point_index > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущая точка",
                callback_data=f"admin_route_point:{get_hash_by_route_id(route_id)}:{current_point_index - 1}"[:64]
            )
        )
    
    if current_point_index < total_points - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующая точка ➡️",
                callback_data=f"admin_route_point:{get_hash_by_route_id(route_id)}:{current_point_index + 1}"[:64]
            )
        )
    
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    
    # Кнопка просмотра фотографий (если есть)
    if has_photos:
        keyboard_rows.append([
            InlineKeyboardButton(
                text="📸 Просмотреть фотографии",
                callback_data=f"admin_view_photos:{get_hash_by_route_id(route_id)}:{current_point_index}"[:64]
            )
        ])
    
    # Кнопка просмотра данных лабораторий (если есть)
    if has_lab_data:
        keyboard_rows.append([
            InlineKeyboardButton(
                text="🏥 Данные лабораторий",
                callback_data=f"admin_lab_data:{get_hash_by_route_id(route_id)}"
            )
        ])
    
    # Кнопка возврата к списку маршрутов
    keyboard_rows.append([
        InlineKeyboardButton(
            text="📋 К списку маршрутов",
            callback_data="admin_back_to_routes"
        )
    ])
    
    # Кнопка возврата в меню мониторинга
    keyboard_rows.append([
        InlineKeyboardButton(
            text="⬅️ К мониторингу",
            callback_data="routes_monitoring_back"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_admin_photos_viewer_keyboard(
    route_id: str,
    point_index: int,
    current_photo_index: int,
    total_photos: int
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для просмотра фотографий (для админа).
    
    Args:
        route_id: ID маршрута
        point_index: Индекс точки
        current_photo_index: Индекс текущей фотографии
        total_photos: Общее количество фотографий
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации по фотографиям
    """
    keyboard_rows = []
    
    # Кнопки навигации по фотографиям
    nav_buttons = []
    if current_photo_index > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущее фото",
                callback_data=f"admin_photo:{get_hash_by_route_id(route_id)}:{point_index}:{current_photo_index - 1}"
            )
        )
    
    if current_photo_index < total_photos - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующее фото ➡️",
                callback_data=f"admin_photo:{get_hash_by_route_id(route_id)}:{point_index}:{current_photo_index + 1}"
            )
        )
    
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    
    # Кнопка возврата к деталям точки
    keyboard_rows.append([
        InlineKeyboardButton(
            text="⬅️ К деталям точки",
            callback_data=f"admin_route_point:{get_hash_by_route_id(route_id)}:{point_index}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

def get_route_id_by_hash(route_hash: str) -> str:
    """Получает полный route_id по хешу."""
    return _route_hash_map.get(route_hash, route_hash)


def get_hash_by_route_id(route_id: str) -> str:
    """Получает хеш по полному route_id."""
    import hashlib
    import re
    
    # Очищаем route_id от потенциально проблемных символов
    clean_route_id = re.sub(r'[^\w\-_.]', '_', str(route_id))
    route_hash = hashlib.md5(clean_route_id.encode()).hexdigest()[:8]
    
    # Сохраняем соответствие с оригинальным route_id
    _route_hash_map[route_hash] = route_id
    return route_hash
