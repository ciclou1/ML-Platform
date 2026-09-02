import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.user import Role, User
from app.repositories.user import RoleRepository, UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)

    async def list_users(self, offset: int = 0, limit: int = 20) -> list[User]:
        return await self.user_repo.list_with_role(offset=offset, limit=limit)

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self.user_repo.get_with_role(user_id)

    async def create_user(self, username: str, password: str, role_id: uuid.UUID,
                          display_name: str | None = None) -> User:
        if await self.user_repo.get_by_username(username):
            raise ConflictError(f"用户名已存在: {username}")
        if not await self.role_repo.get_by_id(role_id):
            raise NotFoundError("所选角色不存在")
        user = await self.user_repo.create(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role_id=role_id,
            )
        )
        return await self.user_repo.get_with_role(user.id)

    async def update_user(self, user_id: uuid.UUID, *, display_name: str | None = None,
                          role_id: uuid.UUID | None = None) -> User | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        if role_id is not None:
            role = await self.role_repo.get_by_id(role_id)
            if not role:
                raise NotFoundError("所选角色不存在")
            if user.username == "admin" and role.name != "admin":
                raise ValidationError("不能移除内置管理员的管理员角色")
            user.role_id = role_id
        if display_name is not None:
            user.display_name = display_name
        await self.user_repo.update(user)
        return await self.user_repo.get_with_role(user_id)

    async def reset_password(self, user_id: uuid.UUID, new_password: str) -> User | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        user.password_hash = hash_password(new_password)
        return await self.user_repo.update(user)

    async def set_status(self, user_id: uuid.UUID, status: str,
                         *, operator_username: str | None = None) -> User | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        if operator_username and user.username == operator_username:
            raise ValidationError("不能禁用当前登录账号")
        if user.username == "admin" and status == "disabled":
            raise ValidationError("不能禁用内置管理员账号")
        user.status = status
        return await self.user_repo.update(user)

    async def delete_user(self, user_id: uuid.UUID,
                          *, operator_username: str | None = None) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False
        if user.username == "admin":
            raise ValidationError("不能删除内置管理员账号")
        if operator_username and user.username == operator_username:
            raise ValidationError("不能删除当前登录账号")
        await self.user_repo.delete(user)
        return True

    async def authenticate(self, username: str, password: str) -> User:
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            raise ValidationError("用户名或密码错误")
        if user.status != "active":
            raise ValidationError("账号已被禁用")
        user.last_login_at = datetime.now(UTC)
        await self.user_repo.update(user)
        return await self.user_repo.get_with_role(user.id)

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password_hash):
            raise ValidationError("原密码不正确")
        user.password_hash = hash_password(new_password)
        await self.user_repo.update(user)

    async def count_admin_actors(self) -> int:
        return await self.user_repo.count()


class RoleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.role_repo = RoleRepository(session)
        self.user_repo = UserRepository(session)

    async def list_roles(self, offset: int = 0, limit: int = 100) -> list[tuple[Role, int]]:
        return await self.role_repo.list_with_user_counts(offset=offset, limit=limit)

    async def get_role(self, role_id: uuid.UUID) -> Role | None:
        return await self.role_repo.get_by_id(role_id)

    async def create_role(self, name: str, permissions: list[str],
                          description: str | None = None) -> Role:
        if await self.role_repo.get_by_name(name):
            raise ConflictError(f"角色名已存在: {name}")
        return await self.role_repo.create(
            Role(name=name, description=description, permissions=permissions)
        )

    async def update_role(self, role_id: uuid.UUID, *, name: str | None = None,
                          description: str | None = None,
                          permissions: list[str] | None = None) -> Role | None:
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            return None
        if name is not None and name != role.name:
            if role.is_builtin:
                raise ValidationError("内置角色不能重命名")
            if await self.role_repo.get_by_name(name):
                raise ConflictError(f"角色名已存在: {name}")
            role.name = name
        if description is not None:
            role.description = description
        if permissions is not None:
            role.permissions = permissions
        return await self.role_repo.update(role)

    async def delete_role(self, role_id: uuid.UUID) -> bool:
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            return False
        if role.is_builtin:
            raise ValidationError("内置角色不能删除")
        if await self.user_repo.count_by_role(role_id) > 0:
            raise ValidationError("该角色下仍有用户，请先转移用户")
        await self.role_repo.delete(role)
        return True
