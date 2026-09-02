"""认证安全与中间件白名单测试（纯函数，无 DB 依赖）。"""

from __future__ import annotations

import pytest

from app.core.auth_middleware import extract_bearer_token, is_public_path
from app.core.security import (
    PERMISSIONS,
    create_access_token,
    decode_access_token,
    has_permission,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_and_verify(self) -> None:
        hashed = hash_password("admin123")

        assert hashed != "admin123"
        assert verify_password("admin123", hashed)
        assert not verify_password("wrong", hashed)

    def test_verify_invalid_hash_returns_false(self) -> None:
        assert not verify_password("x", "not-a-hash")


class TestJwt:
    def test_create_and_decode(self) -> None:
        import uuid

        token = create_access_token(uuid.uuid4(), "admin")
        payload = decode_access_token(token)

        assert payload is not None
        assert payload["username"] == "admin"

    def test_tampered_token_rejected(self) -> None:
        import uuid

        token = create_access_token(uuid.uuid4(), "admin")

        assert decode_access_token(token + "x") is None

    def test_expired_token_rejected(self, monkeypatch) -> None:
        import uuid

        from app.config import settings

        monkeypatch.setattr(settings, "jwt_expire_minutes", -1)
        token = create_access_token(uuid.uuid4(), "admin")

        assert decode_access_token(token) is None

    def test_garbage_token_rejected(self) -> None:
        assert decode_access_token("garbage") is None


class TestPermission:
    def test_wildcard_matches_everything(self) -> None:
        assert has_permission(["*"], "system:manage")
        assert has_permission(["*"], "dataset:write")

    def test_specific_permission(self) -> None:
        assert has_permission(["dataset:read"], "dataset:read")
        assert not has_permission(["dataset:read"], "dataset:write")

    def test_empty_permissions(self) -> None:
        assert not has_permission([], "dataset:read")

    def test_permission_catalog(self) -> None:
        assert "system:manage" in PERMISSIONS
        assert "dataset:read" in PERMISSIONS


class TestPublicPath:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/auth/login",
            "/api/v1/health",
            "/api/v1/nodes",
            "/api/v1/nodes/heartbeat",
            "/api/v1/ws/tasks/abc",
            "/docs",
            "/openapi.json",
        ],
    )
    def test_public_paths(self, path: str) -> None:
        assert is_public_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/datasets",
            "/api/v1/users",
            "/api/v1/auth/me",
            "/api/v1/auth/change-password",
            "/api/v1/tasks",
        ],
    )
    def test_protected_paths(self, path: str) -> None:
        assert not is_public_path(path)


class TestBearerToken:
    def test_extract(self) -> None:
        assert extract_bearer_token("Bearer abc") == "abc"

    def test_extract_rejects_other_scheme(self) -> None:
        assert extract_bearer_token("Basic abc") is None
        assert extract_bearer_token(None) is None
        assert extract_bearer_token("Bearer ") is None
