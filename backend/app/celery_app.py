"""Celery-приложение. В Спринте 0-1 задач нет, очередь поднята под следующие спринты (OCR, генерация DOCX)."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()
redis_url = getattr(settings, "redis_url", "redis://localhost:6379/0")

celery_app = Celery(
    "stroydoc",
    broker=redis_url,
    backend=redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
