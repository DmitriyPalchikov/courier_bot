# 🐛 Исправление ошибки "there is no text in the message to edit"

## ❌ **Ошибка:**
```
Bad Request: there is no text in the message to edit
Route ID: 1066894931_Москва_20250928_160605_04777141, Point index: 0, Total points: 2
```

## 🔍 **Причина:**
Ошибка возникала при нажатии кнопки "К деталям точки" в просмотрщике фотографий. Telegram не позволяет использовать `edit_text()` для сообщений, которые содержат фото, так как у них нет текста для редактирования.

## 🔧 **Исправление в `admin_show_route_point_details()`:**

```python
try:
    # Проверяем, содержит ли сообщение фото
    if callback.message.photo:
        # Если это сообщение с фото, отправляем новое текстовое сообщение
        await callback.message.answer(
            text=message_text,
            reply_markup=keyboard
        )
        # Удаляем старое сообщение с фото
        try:
            await callback.message.delete()
        except:
            pass  # Игнорируем ошибку удаления
    else:
        # Если это текстовое сообщение, редактируем его
        await callback.message.edit_text(
            text=message_text,
            reply_markup=keyboard
        )
except Exception as e:
    # Fallback: отправляем новое сообщение
    await callback.message.answer(
        text=message_text,
        reply_markup=keyboard
    )
```

## 🎯 **Логика исправления:**

1. **Проверка типа сообщения**: `if callback.message.photo:`
2. **Для фото-сообщений**: Отправляем новое текстовое сообщение + удаляем старое
3. **Для текстовых сообщений**: Используем стандартный `edit_text()`
4. **Fallback**: Если что-то пошло не так, отправляем новое сообщение

## ✅ **Результат:**
- ✅ Переход от фотографии к деталям точки работает без ошибок
- ✅ Навигация между текстовыми сообщениями остается быстрой (edit_text)
- ✅ Robust fallback механизм для любых неожиданных ситуаций
- ✅ Старые фото-сообщения автоматически удаляются

## 🔄 **Затронутые функции:**
- `admin_show_route_point_details()` - основное исправление
- `admin_navigate_route_point()` - использует исправленную функцию
- Кнопка "⬅️ К деталям точки" в просмотрщике фотографий

---
**Статус:** ✅ Исправлено и протестировано  
**Дата:** 28.09.2025

