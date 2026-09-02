"""认证中间件：全站强制登录 + 写操作审计日志。

- 白名单前缀之外的所有 API 请求需携带 JWT（Authorization: Bearer 或 ?access_token=，
  后者供 <img>/window.open 等无法携带请求头的文件流场景）。
- 非 GET/HEAD/OPTIONS 请求完成后用独立 session 写入 audit_logs，
  审计失败仅记录告警，不影响主请求。
"""

from __future__ import annotations

import logging
import time
from urllib.parse import parse_qs

from app.core.security import decode_access_token
from app.db.postgres import async_session_factory
from app.models.user import AuditLog
from app.repositories.user import AuditLogRepository

logger = logging.getLogger(__name__)

PUBLIC_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/health",
    "/api/v1/nodes",
    "/api/v1/ws",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_AUDIT_SKIP_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/api/v1/health")


def is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PUBLIC_PREFIXES)


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _query_token(scope) -> str | None:
    values = parse_qs(scope.get("query_string", b"").decode("latin-1")).get("access_token")
    return values[0] if values else None


class AuthAuditMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()

        if not is_public_path(path):
            headers = _headers(scope)
            token = extract_bearer_token(headers.get("authorization")) or _query_token(scope)
            payload = decode_access_token(token) if token else None
            if payload is None:
                await _send_401(send)
                return
            scope.setdefault("state", {})
            scope["state"]["auth_username"] = payload.get("username")
            scope["state"]["auth_user_id"] = payload.get("sub")

        if method in {"GET", "HEAD", "OPTIONS"} or _should_skip_audit(path):
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            username = scope.get("state", {}).get("auth_username")
            await self._write_audit(scope, method, path, status_holder["status"], started, username)

    async def _write_audit(self, scope, method: str, path: str, status_code: int,
                           started: float, username: str | None) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        query_string = scope.get("query_string", b"").decode("latin-1")
        headers = _headers(scope)
        ip = headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip and scope.get("client"):
            ip = scope["client"][0]

        try:
            async with async_session_factory() as session:
                await AuditLogRepository(session).create(
                    AuditLog(
                        username=username,
                        method=method,
                        path=path[:500],
                        query=query_string[:1000] or None,
                        status_code=status_code,
                        ip=ip or None,
                        duration_ms=duration_ms,
                    )
                )
                await session.commit()
        except Exception as exc:  # 审计是旁路，不影响主请求
            logger.warning("Failed to write audit log: %s", exc)


def _headers(scope) -> dict[str, str]:
    return {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


def _should_skip_audit(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _AUDIT_SKIP_PREFIXES)


async def _send_401(send) -> None:
    body = '{"detail":"未登录或登录已过期"}'.encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
