import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node import Node, NodeDeployment
from app.repositories.base import BaseRepository


class NodeRepository(BaseRepository[Node]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Node)

    async def get_by_token_hash(self, token_hash: str) -> Node | None:
        stmt = select(Node).where(Node.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class NodeDeploymentRepository(BaseRepository[NodeDeployment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, NodeDeployment)

    async def list_by_node(self, node_id: uuid.UUID) -> list[NodeDeployment]:
        stmt = (
            select(NodeDeployment)
            .where(NodeDeployment.node_id == node_id)
            .order_by(NodeDeployment.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
