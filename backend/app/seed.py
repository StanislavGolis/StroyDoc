"""Seed: создаёт компанию по умолчанию и администратора (из переменных окружения).

Запуск: python -m app.seed
"""

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Company, User
from app.models.enums import UserRole


def seed() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        company = db.scalar(select(Company).where(Company.name == settings.default_company_name))
        if company is None:
            company = Company(name=settings.default_company_name)
            db.add(company)
            db.commit()
            db.refresh(company)
            print(f"Создана компания: {company.name} (id={company.id})")

        email = settings.admin_email.lower()
        admin = db.scalar(
            select(User).where(User.company_id == company.id, User.email == email)
        )
        if admin is None:
            admin = User(
                company_id=company.id,
                email=email,
                full_name=settings.admin_full_name,
                role=UserRole.ADMIN,
                password_hash=hash_password(settings.admin_password),
            )
            db.add(admin)
            db.commit()
            print(f"Создан администратор: {email}")
        else:
            print(f"Администратор уже существует: {email}")


if __name__ == "__main__":
    seed()
