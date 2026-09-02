import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import has_permission
from app.db.postgres import get_session
from app.exceptions import ForbiddenError
from app.models.user import User
from app.repositories.user import UserRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(request: Request, db: DbSession) -> User:
    user_id = getattr(request.state, "auth_user_id", None)
    if not user_id:
        raise ForbiddenError("未认证")
    user = await UserRepository(db).get_with_role(uuid.UUID(str(user_id)))
    if not user or user.status != "active":
        raise ForbiddenError("用户不存在或已禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str):
    async def dependency(user: CurrentUser) -> User:
        if not has_permission(list(user.role.permissions or []), permission):
            raise ForbiddenError(f"缺少权限: {permission}")
        return user

    return dependency
