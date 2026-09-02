import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import AuditLog, Role, User
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Role)

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_user_counts(
        self, offset: int = 0, limit: int = 100
    ) -> list[tuple[Role, int]]:
        stmt = (
            select(Role, func.count(User.id))
            .outerjoin(User, User.role_id == Role.id)
            .group_by(Role.id)
            .order_by(Role.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(role, count) for role, count in result.all()]


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_role(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_role(self, offset: int = 0, limit: int = 20) -> list[User]:
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .order_by(User.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_role(self, role_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(User).where(User.role_id == role_id)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def search(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        username: str | None = None,
        method: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        conditions = []
        if username:
            conditions.append(AuditLog.username == username)
        if method:
            conditions.append(AuditLog.method == method)

        base = select(func.count()).select_from(AuditLog)
        if conditions:
            base = base.where(*conditions)
        total = int((await self.session.execute(base)).scalar_one())

        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        if conditions:
            stmt = stmt.where(*conditions)
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows, total
