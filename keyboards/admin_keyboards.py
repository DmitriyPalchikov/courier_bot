"""
Клавиатуры для административной панели курьерского бота.

Содержит функции для создания специализированных клавиатур
для администраторов системы.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт главную клавиатуру административной панели.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура админ-панели
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="admin_statistics"
        ),
        InlineKeyboardButton(
            text="🚚 Доставки в Москву",
            callback_data="admin_deliveries"
        ),
        InlineKeyboardButton(
            text="👥 Пользователи",
            callback_data="admin_users"
        ),
        InlineKeyboardButton(
            text="📋 Активные маршруты",
            callback_data="admin_active_routes"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="admin_settings"
        ),
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data="main_menu"
        )
    )
    
    builder.adjust(2, 2, 1, 1)
    
    return builder.as_markup()


def get_statistics_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для раздела статистики.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура статистики
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="📈 Детальная статистика",
            callback_data="detailed_stats"
        ),
        InlineKeyboardButton(
            text="📅 За период",
            callback_data="period_stats"
        ),
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="admin_statistics"
        ),
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_menu"
        )
    )
    
    builder.adjust(2, 1, 1)
    
    return builder.as_markup()


def get_deliveries_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для управления доставками.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура доставок
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(
            text="✅ Подтвердить доставки",
            callback_data="confirm_deliveries"
        ),
        InlineKeyboardButton(
            text="🖨️ Печать маршрутного листа",
            callback_data="print_route_list"
        ),
        InlineKeyboardButton(
            text="📋 История доставок",
            callback_data="delivery_history"
        ),
        InlineKeyboardButton(
            text="🔄 Обновить список",
            callback_data="admin_deliveries"
        ),
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_menu"
        )
    )
    
    builder.adjust(1, 1, 1, 1, 1)
    
    return builder.as_markup()
