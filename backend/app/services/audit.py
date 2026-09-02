from sqlalchemy import delete

from app.models.user import AuditLog
from app.repositories.user import AuditLogRepository


class AuditService:
    def __init__(self, session) -> None:
        self.session = session
        self.repo = AuditLogRepository(session)

    async def search(self, *, offset: int = 0, limit: int = 20,
                     username: str | None = None, method: str | None = None):
        return await self.repo.search(
            offset=offset, limit=limit, username=username, method=method
        )

    async def create(self, **fields) -> AuditLog:
        return await self.repo.create(AuditLog(**fields))

    async def clear(self) -> None:
        await self.session.execute(delete(AuditLog))
        await self.session.flush()
