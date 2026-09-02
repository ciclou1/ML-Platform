import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_permission
from app.exceptions import NotFoundError
from app.schemas.user import RoleCreate, RoleResponse, RoleUpdate
from app.services.user import RoleService

router = APIRouter(prefix="/roles", tags=["系统管理"])


def get_service(db: DbSession) -> RoleService:
    return RoleService(db)


@router.get("", response_model=list[RoleResponse], summary="查询角色列表")
async def list_roles(
    _: CurrentUser,
    service: RoleService = Depends(get_service),
):
    roles = await service.list_roles()
    responses: list[RoleResponse] = []
    for role, count in roles:
        response = RoleResponse.model_validate(role)
        response.user_count = count
        responses.append(response)
    return responses


@router.post("", response_model=RoleResponse, status_code=201, summary="创建角色")
async def create_role(
    data: RoleCreate,
    _: Any = Depends(require_permission("system:manage")),
    service: RoleService = Depends(get_service),
):
    return await service.create_role(data.name, data.permissions, data.description)


@router.put("/{role_id}", response_model=RoleResponse, summary="更新角色")
async def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    _: Any = Depends(require_permission("system:manage")),
    service: RoleService = Depends(get_service),
):
    entity = await service.update_role(
        role_id, name=data.name, description=data.description, permissions=data.permissions
    )
    if not entity:
        raise NotFoundError("角色不存在")
    return RoleResponse.model_validate(entity)


@router.delete("/{role_id}", status_code=204, summary="删除角色")
async def delete_role(
    role_id: uuid.UUID,
    _: Any = Depends(require_permission("system:manage")),
    service: RoleService = Depends(get_service),
) -> None:
    deleted = await service.delete_role(role_id)
    if not deleted:
        raise NotFoundError("角色不存在")
