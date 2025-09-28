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