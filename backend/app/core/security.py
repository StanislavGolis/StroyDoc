"""Хеширование паролей, JWT-токены, работа с refresh-cookie."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from fastapi import Response

from app.core.config import get_settings
from app.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(subject: str, token_type: str, expires_delta: timedelta, user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(subject),
        "type": token_type,
        "jti": str(uuid4()),  # уникальный id — ротация токенов не даёт коллизий в пределах секунды
        "company_id": user.company_id,
        "role": user.role,
        "ver": user.token_version,
        "iat": _now(),
        "exp": _now() + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User) -> str:
    settings = get_settings()
    return _encode(user.id, "access", timedelta(minutes=settings.access_token_expire_minutes), user)


def create_refresh_token(user: User) -> str:
    settings = get_settings()
    return _encode(user.id, "refresh", timedelta(days=settings.refresh_token_expire_days), user)


def decode_token(token: str, expected_type: str) -> dict:
    """Декодирует токен. Поднимает jwt.PyJWTError при невалидности."""
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_same_site,
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.cookie_name, path="/api/v1/auth")
