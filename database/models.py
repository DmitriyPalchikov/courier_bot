"""
Модели базы данных для Telegram-бота курьерской службы.

Этот файл содержит определения всех таблиц базы данных используя SQLAlchemy ORM.
Каждая модель представляет собой таблицу в базе данных.

Используемые модели:
- User: Информация о пользователях (курьерах)
- Route: Информация о маршрутах
- RouteProgress: Прогресс прохождения маршрута
- Delivery: Информация о доставках в Москву
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Integer, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """
    Базовый класс для всех моделей базы данных.
    
    AsyncAttrs - добавляет поддержку асинхронных операций
    DeclarativeBase - базовый класс для декларативного стиля SQLAlchemy
    """
    
    # Автоматически добавляем поля created_at и updated_at ко всем моделям
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        comment="Время создания записи"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        comment="Время последнего обновления записи"
    )


class User(Base):
    """
    Модель пользователя (курьера).
    
    Содержит информацию о курьерах, использующих бота.
    """
    __tablename__ = 'users'
    
    # Уникальный идентификатор пользователя в Telegram (первичный ключ)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True,
        comment="Telegram ID пользователя"
    )
    
    # Имя пользователя из Telegram
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Username пользователя в Telegram"
    )
    
    # Полное имя пользователя
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True, 
        comment="Полное имя пользователя"
    )
    
    # Статус пользователя (активный/заблокированный)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Активен ли пользователь"
    )
    
    # Является ли пользователь администратором
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Является ли пользователь администратором"
    )
    
    # Связь с прогрессом маршрутов (один пользователь - много прогрессов)
    route_progresses: Mapped[list["RouteProgress"]] = relationship(
        "RouteProgress",
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """Строковое представление пользователя для отладки"""
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"


class Route(Base):
    """
    Модель маршрута.
    
    Содержит информацию о доступных маршрутах и точках сбора товаров.
    """
    __tablename__ = 'routes'
    
    # Уникальный идентификатор маршрута
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный ID маршрута"
    )
    
    # Название города маршрута
    city_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Название города маршрута"
    )
    
    # Название точки (организации)
    point_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Название точки сбора"
    )
    
    # Адрес точки сбора
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Полный адрес точки сбора"
    )
    
    # Организация (КДЛ, Ховер, Дартис)
    organization: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Название организации"
    )
    
    # Географические координаты (широта)
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Широта точки сбора"
    )
    
    # Географические координаты (долгота)
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Долгота точки сбора"
    )
    
    # Порядок объезда в маршруте
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Порядковый номер в маршруте"
    )
    
    # Активна ли точка маршрута
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Активна ли точка маршрута"
    )
    
    # Связь с прогрессом (одна точка - много прогрессов от разных пользователей)
    route_progresses: Mapped[list["RouteProgress"]] = relationship(
        "RouteProgress",
        back_populates="route"
    )
    
    def __repr__(self) -> str:
        """Строковое представление маршрута для отладки"""
        return f"<Route(city='{self.city_name}', point='{self.point_name}')>"


class RouteProgress(Base):
    """
    Модель прогресса прохождения маршрута.
    
    Отслеживает, какие точки маршрута пользователь уже посетил,
    сколько коробок собрал и когда это было сделано.
    """
    __tablename__ = 'route_progress'
    
    # Уникальный идентификатор записи прогресса
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный ID записи прогресса"
    )
    
    # Связь с пользователем (внешний ключ)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('users.telegram_id', ondelete='CASCADE'),
        nullable=False,
        comment="ID пользователя"
    )
    
    # Связь с точкой маршрута (внешний ключ) 
    route_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('routes.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID точки маршрута"
    )
    
    # Уникальный ID сессии маршрута (для группировки точек одного маршрута)
    route_session_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Уникальный ID сессии маршрута"
    )
    
    # Количество собранных контейнеров
    containers_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Количество собранных контейнеров"
    )
    
    # Связь с фотографиями (одна запись прогресса - много фотографий)
    photos: Mapped[list["RoutePhoto"]] = relationship(
        "RoutePhoto",
        back_populates="route_progress",
        cascade="all, delete-orphan",
        order_by="RoutePhoto.photo_order"
    )
    
    # Статус выполнения точки маршрута
    status: Mapped[str] = mapped_column(
        String(20),
        default='completed',
        comment="Статус: completed, pending, skipped"
    )
    
    # Время посещения точки
    visited_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        comment="Время посещения точки"
    )
    
    # Дополнительные заметки курьера
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Дополнительные заметки курьера"
    )
    
    # Связи с другими моделями
    user: Mapped["User"] = relationship(
        "User",
        back_populates="route_progresses"
    )
    
    route: Mapped["Route"] = relationship(
        "Route", 
        back_populates="route_progresses"
    )
    
    def __repr__(self) -> str:
        """Строковое представление прогресса для отладки"""
        return f"<RouteProgress(user_id={self.user_id}, route_id={self.route_id}, containers={self.containers_count})>"


class RoutePhoto(Base):
    """
    Модель для хранения фотографий с точек маршрута.
    
    Позволяет хранить несколько фотографий для каждой точки маршрута.
    """
    __tablename__ = 'route_photos'
    
    # Уникальный идентификатор фотографии
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный ID фотографии"
    )
    
    # Связь с записью прогресса маршрута
    route_progress_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('route_progress.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID записи прогресса маршрута"
    )
    
    # ID фотографии в Telegram
    photo_file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="File ID фотографии в Telegram"
    )
    
    # Порядковый номер фотографии
    photo_order: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Порядковый номер фотографии"
    )
    
    # Описание фотографии (опционально)
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Описание фотографии"
    )
    
    # Связь с прогрессом маршрута
    route_progress: Mapped["RouteProgress"] = relationship(
        "RouteProgress",
        back_populates="photos"
    )
    
    def __repr__(self) -> str:
        """Строковое представление фотографии для отладки"""
        return f"<RoutePhoto(id={self.id}, route_progress_id={self.route_progress_id}, order={self.photo_order})>"


class Delivery(Base):
    """
    Модель доставки в Москву.
    
    Содержит информацию о сформированных маршрутных листах
    для доставки собранных товаров в Москву.
    """
    __tablename__ = 'deliveries'
    
    # Уникальный идентификатор доставки
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный ID доставки"
    )
    
    # Дата формирования маршрутного листа
    delivery_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        comment="Дата формирования доставки"
    )
    
    # Организация получатель (КДЛ, Ховер, Дартис)
    organization: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Организация получатель"
    )
    
    # Общее количество контейнеров для доставки
    total_containers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Общее количество контейнеров"
    )
    
    # Адрес доставки в Москве
    delivery_address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Адрес доставки в Москве"
    )
    
    # Контактная информация получателя
    contact_info: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Контактная информация получателя"
    )
    
    # Статус доставки
    status: Mapped[str] = mapped_column(
        String(20),
        default='pending',
        comment="Статус: pending, in_progress, completed, cancelled"
    )
    
    # Курьер ответственный за доставку в Москву
    courier_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey('users.telegram_id'),
        nullable=True,
        comment="ID курьера для доставки в Москву"
    )
    
    # Время фактической доставки
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Время фактической доставки"
    )
    
    def __repr__(self) -> str:
        """Строковое представление доставки для отладки"""
        return f"<Delivery(id={self.id}, org='{self.organization}', containers={self.total_containers})>"
