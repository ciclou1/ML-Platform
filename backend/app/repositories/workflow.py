from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.repositories.base import BaseRepository


class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workflow)

    async def list_all(self, offset: int = 0, limit: int = 100) -> list[Workflow]:
        return await self.list(offset=offset, limit=limit)
