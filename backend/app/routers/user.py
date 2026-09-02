import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_permission
from app.exceptions import NotFoundError
from app.schemas.user import (
    UserCreate,
    UserPasswordReset,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["系统管理"])


def get_service(db: DbSession) -> UserService:
    return UserService(db)


@router.get("", response_model=list[UserResponse], summary="查询用户列表")
async def list_users(
    _: CurrentUser,
    page: int = 1,
    page_size: int = 50,
    service: UserService = Depends(get_service),
):
    return await service.list_users(offset=(page - 1) * page_size, limit=page_size)


@router.post("", response_model=UserResponse, status_code=201, summary="创建用户")
async def create_user(
    data: UserCreate,
    _: Any = Depends(require_permission("system:manage")),
    service: UserService = Depends(get_service),
):
    return await service.create_user(data.username, data.password, data.role_id, data.display_name)


@router.put("/{user_id}", response_model=UserResponse, summary="更新用户信息")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    _: Any = Depends(require_permission("system:manage")),
    service: UserService = Depends(get_service),
):
    entity = await service.update_user(
        user_id, display_name=data.display_name, role_id=data.role_id
    )
    if not entity:
        raise NotFoundError("用户不存在")
    return entity


@router.put("/{user_id}/password", response_model=UserResponse, summary="重置用户密码")
async def reset_password(
    user_id: uuid.UUID,
    data: UserPasswordReset,
    _: Any = Depends(require_permission("system:manage")),
    service: UserService = Depends(get_service),
):
    entity = await service.reset_password(user_id, data.password)
    if not entity:
        raise NotFoundError("用户不存在")
    return entity


@router.put("/{user_id}/status", response_model=UserResponse, summary="启用/禁用用户")
async def set_status(
    user_id: uuid.UUID,
    data: UserStatusUpdate,
    operator: Any = Depends(require_permission("system:manage")),
    service: UserService = Depends(get_service),
):
    entity = await service.set_status(user_id, data.status, operator_username=operator.username)
    if not entity:
        raise NotFoundError("用户不存在")
    return entity


@router.delete("/{user_id}", status_code=204, summary="删除用户")
async def delete_user(
    user_id: uuid.UUID,
    operator: Any = Depends(require_permission("system:manage")),
    service: UserService = Depends(get_service),
) -> None:
    deleted = await service.delete_user(user_id, operator_username=operator.username)
    if not deleted:
        raise NotFoundError("用户不存在")
