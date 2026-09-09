"""Абстракция объектного хранилища: local (dev/тесты) или MinIO (docker/prod)."""

from functools import lru_cache
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings


class StorageError(Exception):
    pass


class Storage:
    """Интерфейс хранилища."""

    def put_stream(self, key: str, stream: BinaryIO, length: int) -> None:
        raise NotImplementedError

    def open_stream(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalStorage(Storage):
    """Хранилище на локальном диске (dev, автотесты)."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # защита от path traversal
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise StorageError("Некорректный ключ хранилища")
        return path

    def put_stream(self, key: str, stream: BinaryIO, length: int) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            remaining = length
            while remaining > 0:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                out.write(chunk)
                remaining -= len(chunk)

    def open_stream(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class MinioStorage(Storage):
    """Хранилище в MinIO (S3-совместимое)."""

    def __init__(self) -> None:
        from minio import Minio

        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_stream(self, key: str, stream: BinaryIO, length: int) -> None:
        import io

        if isinstance(stream, io.BytesIO):
            data = stream
        else:
            data = stream
        self.client.put_object(self.bucket, key, data, length=length)

    def open_stream(self, key: str) -> BinaryIO:
        import urllib3

        resp = self.client.get_object(self.bucket, key)
        if isinstance(resp, urllib3.HTTPResponse):
            return resp  # type: ignore[return-value]
        raise StorageError("Не удалось открыть объект")

    def delete(self, key: str) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Не удалось удалить объект: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:  # noqa: BLE001
            return False


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "minio":
        return MinioStorage()
    return LocalStorage(settings.storage_local_dir)
