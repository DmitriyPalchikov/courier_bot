# Клонируем репозиторий
```bash
git clone <your-repo-url>
cd courier-bot
```

# Создаём виртуальное окружение
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Устанавливаем зависимости
pip install -r requirements.txt

pip install aiogram aiosqlite python-dotenv sqlalchemy

# Настраиваем переменные окружения
cp .env.example .env
# Редактируем .env и добавляем токен бота
```