import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.algorithm_package import AlgorithmPackage, AlgorithmPackageVersion
from app.repositories.base import BaseRepository


class AlgorithmPackageRepository(BaseRepository[AlgorithmPackage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AlgorithmPackage)

    async def get_by_name(self, name: str) -> AlgorithmPackage | None:
        stmt = select(AlgorithmPackage).where(AlgorithmPackage.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AlgorithmPackageVersionRepository(BaseRepository[AlgorithmPackageVersion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AlgorithmPackageVersion)

    async def list_by_package(self, package_id: uuid.UUID) -> list[AlgorithmPackageVersion]:
        stmt = (
            select(AlgorithmPackageVersion)
            .where(AlgorithmPackageVersion.package_id == package_id)
            .order_by(AlgorithmPackageVersion.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
