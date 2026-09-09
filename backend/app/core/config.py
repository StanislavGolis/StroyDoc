from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "СтройДок API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    # БД. По умолчанию — docker-compose (хост db). Для локального запуска:
    # postgresql+psycopg://stroydoc:stroydoc@localhost:5432/stroydoc
    database_url: str = "postgresql+psycopg://stroydoc:stroydoc@db:5432/stroydoc"

    # JWT
    secret_key: str = "dev-secret-change-me-please-use-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Хранилище файлов
    storage_backend: str = "local"  # local | minio
    storage_local_dir: str = "./storage"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "stroydoc"
    minio_secure: bool = False
    object_storage_quota_bytes: int = 10 * 1024 * 1024 * 1024  # 10 ГБ на объект
    max_file_size_bytes: int = 100 * 1024 * 1024  # 100 МБ (реальные сканы паспортов)
    max_zip_size_bytes: int = 1024 * 1024 * 1024  # 1 ГБ (архивы паспортов)

    # Cookies
    cookie_name: str = "stroydoc_refresh"
    cookie_secure: bool = False
    cookie_same_site: str = "lax"

    # CORS (JSON-список, напр. ["http://localhost:3000"])
    cors_origins: list[str] = ["http://localhost:3000"]

    # Seed
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    admin_full_name: str = "Администратор системы"
    default_company_name: str = "Компания по умолчанию"


@lru_cache
def get_settings() -> Settings:
    return Settings()
