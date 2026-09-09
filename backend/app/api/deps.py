"""FastAPI-зависимости: текущий пользователь, роли, доступ к объекту."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import ConstructionObject, ObjectAssignment, User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Не удалось проверить учётные данные") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        payload = decode_token(credentials.credentials, "access")
    except jwt.PyJWTError:
        raise _unauthorized() from None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("Пользователь не найден или деактивирован")
    return user


def require_manager(user: User = Depends(get_current_user)) -> User:
    """Только Руководитель ПТО / Администратор."""
    if not user.is_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return user


def require_object_access(
    object_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConstructionObject:
    """Объект в границах компании текущего пользователя.

    Менеджер видит любой объект компании; инженер — только назначенный.
    """
    obj = db.get(ConstructionObject, object_id)
    if obj is None or obj.company_id != user.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объект не найден")
    if user.is_manager:
        return obj
    assigned = db.scalar(
        select(ObjectAssignment).where(
            ObjectAssignment.object_id == obj.id,
            ObjectAssignment.user_id == user.id,
        )
    )
    if assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к объекту")
    return obj
