# Исправление ошибки "Мои маршруты"

## Проблемы обнаружены:

### 1. BUTTON_DATA_INVALID ошибка
- **Причина**: Callback data превышали лимит Telegram API в 64 байта
- **Пример проблемного callback**: `view_route:1066894931_Вологда_20250914_143205_a1b2c3d4` (57+ символов)

### 2. Потенциальные проблемы с длинными ID
- `route_session_id` может содержать длинные строки с кириллицей
- Формат: `{user_id}_{city}_{timestamp}_{uuid}` где city может быть "Вологда", "Иваново" и т.д.

## Решения реализованы:

### 1. Создан менеджер коротких callback данных
**Файл**: `utils/callback_manager.py`
- Функция `generate_short_callback()` - создает MD5 хеш (12 символов)
- Функция `parse_callback()` - восстанавливает исходные данные
- Специализированные функции для разных типов callback:
  - `create_route_callback()` - для маршрутов (`r:{hash}`)
  - `create_route_point_callback()` - для точек (`rp:{hash}`)
  - `create_photo_callback()` - для фото (`p:{hash}`)

### 2. Обновлены клавиатуры
**Файл**: `keyboards/user_keyboards.py`
- Заменены длинные callback_data на короткие
- Все функции клавиатур теперь используют менеджер callback

### 3. Обновлены обработчики
**Файл**: `handlers/user_handlers.py`
- `@user_router.callback_query(F.data.startswith("view_route:"))` → `@user_router.callback_query(F.data.startswith("r:"))`
- `@user_router.callback_query(F.data.startswith("route_point:"))` → `@user_router.callback_query(F.data.startswith("rp:"))`
- `@user_router.callback_query(F.data.startswith("view_photo:"))` → `@user_router.callback_query(F.data.startswith("p:"))`
- Добавлен парсинг callback данных через `parse_callback()`

## Результат:
✅ Callback data сократились с 50+ символов до 14 символов (`r:5bf09f3155e4`)  
✅ Все callback data теперь в пределах лимита Telegram (64 байта)  
✅ Бот запускается без ошибок  
✅ Функциональность "Мои маршруты" должна работать корректно  

## Тестирование:
- [x] Синтаксическая проверка всех файлов
- [x] Тест создания коротких callback данных  
- [x] Тест восстановления данных из callback
- [x] Запуск бота без ошибок

## Рекомендации:
1. Протестировать функциональность "Мои маршруты" в реальных условиях
2. Мониторить логи на предмет ошибок BUTTON_DATA_INVALID
3. При добавлении новых callback кнопок использовать менеджер callback данных
