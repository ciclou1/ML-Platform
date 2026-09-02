import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    permissions: list[Any]
    is_builtin: bool
    user_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = None
    role_id: uuid.UUID


class UserUpdate(BaseModel):
    display_name: str | None = None
    role_id: uuid.UUID | None = None


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class UserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    role_id: uuid.UUID
    role_name: str | None = None
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    permissions: list[str]


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    username: str | None
    method: str
    path: str
    query: str | None
    status_code: int
    ip: str | None
    duration_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogPage(BaseModel):
    total: int
    items: list[AuditLogResponse]


class SystemConfigResponse(BaseModel):
    app_name: str
    app_env: str
    storage_backend: str
    storage_root: str
    max_upload_size_mb: int
    postgres_host: str
    postgres_db: str
    versions: dict[str, str]
