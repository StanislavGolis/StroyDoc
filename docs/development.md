# Разработка и запуск

> Репозиторий: монорепо. Спринт 0–1: каркас + ролевая модель (объекты, назначения).

## Структура

```
.
├── backend/           FastAPI + SQLAlchemy 2 + Alembic (app)
│   ├── app/
│   │   ├── api/       роутеры и зависимости доступа
│   │   ├── core/      конфиг, JWT/пароли
│   │   ├── db/        движок, сессии, Base
│   │   ├── models/    ORM (Company, User, ConstructionObject, ObjectAssignment)
│   │   └── schemas/   Pydantic-модели
│   ├── alembic/       миграции
│   └── tests/         pytest (auth, users, objects)
├── frontend/          Next.js (App Router) + Ant Design 5
├── docker-compose.yml PostgreSQL + Redis + MinIO + API + Worker + Frontend
└── docs/
```

## Быстрый старт (всё в Docker)

```bash
cp .env.example .env      # при необходимости поменяйте секреты и пароли
docker compose up --build
```

- Фронтенд: http://localhost:3000
- Swagger API: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minioadmin/minioadmin)

Миграции и seed выполняются вручную (в Спринте 0-1 автоматический прогон при старте не реализован):

```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed
```

Учётные данные администратора по умолчанию: `admin@example.com` / `admin123` (см. `.env`).

## Локальная разработка бэкенда (без Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

Запуск миграций к Postgres из docker-compose (БД уже поднята):

```powershell
$env:DATABASE_URL="postgresql+psycopg://stroydoc:stroydoc@localhost:5432/stroydoc"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

### Тесты

Локально тесты используют sqlite и не требуют Postgres; в CI — реальный Postgres (см. `.github/workflows/ci.yml`).

```bash
cd backend
ruff check .
pytest -q
```

## Локальная разработка фронтенда

Фронтенд проксирует `/api/*` на бэкенд (переменная `API_PROXY_TARGET`, по умолчанию `http://localhost:8000`), поэтому CORS не требуется.

```bash
cd frontend
npm ci
npm run dev        # http://localhost:3000
npm run typecheck  # проверка типов
```

## Ключевые решения Спринта 0-1

- Аутентификация: access JWT (в памяти SPA) + refresh JWT в httpOnly cookie (`SameSite=Lax`).
- Отзыв сессий: `token_version` пользователя — инкрементируется при logout и сбросе пароля.
- Доступ: FastAPI-зависимости (`require_manager`, `require_object_access`). Инженер видит только назначенные объекты, менеджер — все объекты компании; всё в границах `company_id`.
- Пароли пользователям генерирует сервер и показывает один раз при создании/сбросе.
- Мультитенантный UI вне MVP: заложена только модель `company_id`.

## Демо и бэкап

- Демо-сценарий: `docs/demo-runbook.md` (новый объект, загрузка РД из `docs/`, паспорта, акты).
- Бэкап БД перед показом:
  ```bash
  docker compose exec db pg_dump -U stroydoc stroydoc > demo_backup.sql
  ```
- Восстановление:
  ```bash
  docker compose exec -T db psql -U stroydoc stroydoc < demo_backup.sql
  ```
- Миграции при обновлении: `docker compose run --rm api alembic upgrade head`.

