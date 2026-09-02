"""认证安全：密码哈希、JWT 签发/校验与权限点常量。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings

# 权限点目录（前端 config/auth.ts 保持同名同义）
PERMISSIONS: dict[str, str] = {
    "dataset:read": "数据集查看",
    "dataset:write": "数据集管理",
    "annotation:read": "标注查看",
    "annotation:write": "标注管理",
    "model:read": "模型查看",
    "model:write": "模型管理",
    "task:run": "任务管理",
    "node:manage": "边缘节点管理",
    "system:manage": "系统管理",
}
ALL_PERMISSIONS: tuple[str, ...] = tuple(PERMISSIONS)
WILDCARD_PERMISSION = "*"

_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: uuid.UUID, username: str) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码并校验 token，无效/过期返回 None。"""

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("username"), str):
        return None
    return payload


def has_permission(role_permissions: list[str], permission: str) -> bool:
    return WILDCARD_PERMISSION in (role_permissions or []) or permission in (role_permissions or [])
