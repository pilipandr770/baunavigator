# BauNavigator

Умный ИИ-ассистент для строительства дома в Германии (Hessen MVP).

## Быстрый старт

```bash
# 1. Скопируй .env.example → .env и заполни переменные
cp .env.example .env

# 2. Установи зависимости
pip install -r requirements.txt

# 3. Инициализируй базу данных
flask db init
flask db migrate -m "initial"
flask db upgrade

# 4. Запусти
flask run
```

## Структура

```
baunavigator/
├── app/
│   ├── models/
│   │   ├── enums.py          # Все enum-типы (StageKey, ActionMode и т.д.)
│   │   └── models.py         # SQLAlchemy модели (15 таблиц)
│   ├── routes/
│   │   ├── auth.py           # Регистрация / вход
│   │   ├── dashboard.py      # Главная страница
│   │   ├── project.py        # Проекты и этапы
│   │   ├── combined.py       # AI, Outbox, Map, Providers, Webhooks
│   │   └── ...               # Стаб-файлы для импорта
│   ├── services/
│   │   └── ai_service.py     # Claude API интеграция
│   ├── templates/            # Jinja2 шаблоны
│   └── static/               # CSS, JS
├── run.py
├── requirements.txt
├── Dockerfile
├── render.yaml
└── .env.example
```

## Деплой на Render.com

1. Создай новый Web Service из GitHub репозитория
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn --bind 0.0.0.0:$PORT --workers 2 run:app`
4. Добавь переменные окружения из `.env.example`
5. После деплоя выполни: `flask db upgrade`

## После первого запуска

Заполни справочник общин (Gemeinden) через Flask shell:

```python
flask shell
>>> from app import db
>>> from app.models import Gemeinde
>>> g = Gemeinde(name='Frankfurt am Main', land='HE',
...     landkreis='kreisfrei',
...     ags_code='06412000',
...     bauamt_email='bauaufsicht@stadt-frankfurt.de',
...     bauamt_url='https://www.bauaufsicht-frankfurt.de')
>>> db.session.add(g)
>>> db.session.commit()
```

## Ключевые переменные .env

| Переменная | Описание |
|---|---|
| `DATABASE_URL` | PostgreSQL URL от Render.com |
| `ANTHROPIC_API_KEY` | Claude API ключ |
| `SECRET_KEY` | Случайная строка минимум 32 символа |
| `MAIL_*` | SMTP для отправки писем |
| `STRIPE_*` | Для монетизации (опционально) |

## Архитектура ИИ

ИИ работает в трёх режимах (`ActionMode`):
- **autonomous** — делает сам, показывает результат
- **confirmation_required** — готовит черновик, ждёт "Отправить"  
- **human_required** — объясняет почему нужен специалист + предлагает варианты

Все действия логируются в `ai_actions_log`.
Все исходящие письма проходят через `messages_outbox`.
