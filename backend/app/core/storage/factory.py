"""存储后端工厂。

主进程中的业务文件读写统一通过 StorageBackend，
worker 进程允许直接用 Path 同步写任务状态文件（见 .claude/skills/storage-rules.md）。
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any, BinaryIO

from app.config import settings

_COPY_CHUNK_SIZE = 1024 * 1024


class LocalStorageBackend:
    """本地文件系统存储后端，所有路径相对 settings.storage_path。"""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _resolve(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            raise ValueError(f"Storage path must be relative: {relative_path}")
        resolved = (self._root / path).resolve()
        if not resolved.is_relative_to(self._root):
            raise ValueError(f"Storage path escapes storage root: {relative_path}")
        return resolved

    async def exists(self, relative_path: str) -> bool:
        return await asyncio.to_thread(self._resolve(relative_path).exists)

    async def load(self, relative_path: str) -> bytes:
        path = self._resolve(relative_path)
        return await asyncio.to_thread(path.read_bytes)

    async def save(self, relative_path: str, content: bytes) -> Path:
        path = self._resolve(relative_path)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(_write)
        return path

    async def save_stream(
        self,
        relative_path: str,
        source: BinaryIO,
        max_size: int | None = None,
    ) -> str:
        """分块写入上传流，超过 max_size 抛出 ValueError，返回落盘后的完整路径。"""

        path = self._resolve(relative_path)

        def _write_stream() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            try:
                with path.open("wb") as file_obj:
                    while chunk := source.read(_COPY_CHUNK_SIZE):
                        total += len(chunk)
                        if max_size is not None and total > max_size:
                            raise ValueError(f"File exceeds max size: {max_size}")
                        file_obj.write(chunk)
            except Exception:
                path.unlink(missing_ok=True)
                raise

        await asyncio.to_thread(_write_stream)
        return str(path)

    async def delete(self, relative_path: str) -> None:
        path = self._resolve(relative_path)

        def _delete() -> None:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)

        await asyncio.to_thread(_delete)

    async def delete_dir(self, relative_path: str) -> None:
        path = self._resolve(relative_path)

        def _delete_dir() -> None:
            if path.is_dir():
                shutil.rmtree(path)

        await asyncio.to_thread(_delete_dir)


_backend: LocalStorageBackend | None = None


def get_storage() -> LocalStorageBackend:
    """返回进程级共享的存储后端实例，当前仅支持 local。"""

    global _backend
    if _backend is None:
        if settings.storage_backend != "local":
            raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
        _backend = LocalStorageBackend(settings.storage_path)
    return _backend
