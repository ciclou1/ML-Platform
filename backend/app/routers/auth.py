from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import create_access_token
from app.deps import CurrentUser, DbSession
from app.schemas.user import ChangePasswordRequest, LoginRequest, LoginResponse, UserResponse
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["认证"])


def get_service(db: DbSession) -> UserService:
    return UserService(db)


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(data: LoginRequest, service: UserService = Depends(get_service)) -> LoginResponse:
    user = await service.authenticate(data.username, data.password)
    return LoginResponse(
        token=create_access_token(user.id, user.username),
        user=UserResponse.model_validate(user),
        permissions=list(user.role.permissions or []),
    )


@router.get("/me", response_model=UserResponse, summary="当前用户信息")
async def me(user: CurrentUser) -> Any:
    return user


@router.post("/change-password", status_code=204, summary="修改当前用户密码")
async def change_password(
    data: ChangePasswordRequest, user: CurrentUser, service: UserService = Depends(get_service)
) -> None:
    await service.change_password(user, data.old_password, data.new_password)
