"""Общие фикстуры: БД (sqlite по умолчанию, postgres в CI), клиент, пользователи."""

import os
import pathlib
import tempfile

# --- Настройка окружения ДО импорта приложения -----------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-0123456789")
# В CI переменная DATABASE_URL уже задана (postgres). Локально — sqlite-файл.
if "DATABASE_URL" not in os.environ:
    _db_file = pathlib.Path(tempfile.mkdtemp(prefix="stroydoc_tests_")) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.as_posix()}?check_same_thread=false"

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Company, User


@pytest.fixture(scope="session", autouse=True)
def _init_db() -> None:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables(_init_db) -> None:
    """Очистка всех таблиц перед каждым тестом."""
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def company() -> Company:
    with SessionLocal() as db:
        c = Company(name="Тестовая компания")
        db.add(c)
        db.commit()
        db.refresh(c)
        return c


@pytest.fixture
def make_user(company: Company):
    """Фабрика пользователей в БД (пароль всегда pass1234, если не задан)."""

    def _make(
        role: str,
        email: str | None = None,
        password: str = "pass1234",
        full_name: str | None = None,
        active: bool = True,
    ) -> User:
        with SessionLocal() as db:
            user = User(
                company_id=company.id,
                email=email or f"{role}_{os.urandom(3).hex()}@example.com",
                full_name=full_name or f"Пользователь {role}",
                role=role,  # type: ignore[arg-type]
                password_hash=hash_password(password),
                is_active=active,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    return _make


@pytest.fixture
def login(client: TestClient):
    """Возвращает access-токен после логина."""

    def _login(email: str, password: str = "pass1234") -> str:
        resp = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _login


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
