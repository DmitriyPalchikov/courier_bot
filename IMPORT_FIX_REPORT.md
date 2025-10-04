# 🐛 Исправление ошибки импорта `and_`

## ❌ **Ошибка:**
```
NameError: name 'and_' is not defined
File "/handlers/admin_handlers.py", line 925, in admin_view_route_details
```

## 🔍 **Причина:**
В файле `handlers/admin_handlers.py` использовалась функция `and_` из SQLAlchemy, но она не была импортирована.

## ✅ **Исправление:**
Добавил импорт `and_` в строку 23:

```python
# Было:
from sqlalchemy import select

# Стало:
from sqlalchemy import select, and_
```

## 🔧 **Проверка других файлов:**
Убедился, что во всех остальных файлах, где используется `and_`, импорт присутствует:

- ✅ `handlers/user_handlers.py` - импорт есть
- ✅ `utils/route_monitor.py` - импорт есть  
- ✅ `utils/warehouse_manager.py` - импорт есть
- ✅ `utils/route_manager.py` - импорт есть

## 🎯 **Результат:**
- Ошибка `NameError: name 'and_' is not defined` исправлена
- Все SQL-запросы с условиями `and_()` теперь работают корректно
- Код прошел проверку линтера без ошибок

---
**Статус:** ✅ Исправлено и протестировано  
**Дата:** 28.09.2025

