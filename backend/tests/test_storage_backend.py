"""LocalStorageBackend 路径安全与读写行为测试（tmp_path，不依赖真实 storage/）。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.core.storage.factory import LocalStorageBackend


@pytest.fixture
def backend(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(tmp_path)


class TestPathSafety:
    def test_reject_absolute_path(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError):
            backend._resolve("C:/elsewhere/file.bin")

    def test_reject_traversal_escape(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError):
            backend._resolve("../outside.bin")

    def test_accepts_nested_relative_path(self, backend: LocalStorageBackend, tmp_path: Path) -> None:
        resolved = backend._resolve("datasets/abc/data.yaml")
        assert resolved == (tmp_path / "datasets" / "abc" / "data.yaml").resolve()


class TestSaveLoadDelete:
    async def test_save_and_load_roundtrip(self, backend: LocalStorageBackend, tmp_path: Path) -> None:
        content = b"hello storage"
        saved = await backend.save("datasets/abc/data.yaml", content)

        assert saved == (tmp_path / "datasets" / "abc" / "data.yaml").resolve()
        assert await backend.load("datasets/abc/data.yaml") == content
        assert await backend.exists("datasets/abc/data.yaml")

    async def test_delete_file(self, backend: LocalStorageBackend) -> None:
        await backend.save("tasks/1/result.json", b"{}")
        await backend.delete("tasks/1/result.json")

        assert not await backend.exists("tasks/1/result.json")

    async def test_delete_dir(self, backend: LocalStorageBackend) -> None:
        await backend.save("models/m1/a.bin", b"a")
        await backend.save("models/m1/b.bin", b"b")
        await backend.delete_dir("models/m1")

        assert not await backend.exists("models/m1/a.bin")

    async def test_save_stream_enforces_max_size(self, backend: LocalStorageBackend) -> None:
        stream = io.BytesIO(b"x" * 10)

        with pytest.raises(ValueError):
            await backend.save_stream("uploads/a.zip", stream, max_size=5)

        assert not await backend.exists("uploads/a.zip")

    async def test_save_stream_ok(self, backend: LocalStorageBackend, tmp_path: Path) -> None:
        stream = io.BytesIO(b"hello")

        result = await backend.save_stream("uploads/ok.bin", stream, max_size=100)

        assert Path(result) == (tmp_path / "uploads" / "ok.bin").resolve()
        assert (tmp_path / "uploads" / "ok.bin").read_bytes() == b"hello"
