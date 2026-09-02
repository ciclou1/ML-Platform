from __future__ import annotations

import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.annotation_batch import AnnotationReview
from app.models.dataset import Dataset, Image
from app.models.model import MLModel
from app.models.task import Task


class StatsRepository:
    """Read-only aggregate queries used by the dashboard and statistics APIs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_datasets(self) -> int:
        return await self._count(Dataset)

    async def count_images(self) -> int:
        return await self._count(Image)

    async def count_annotated_images(self) -> int:
        annotation_exists = exists(select(Annotation.id).where(Annotation.image_id == Image.id))
        stmt = (
            select(func.count())
            .select_from(Image)
            .where(or_(Image.annotation_status != "unannotated", annotation_exists))
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def count_models(self) -> int:
        return await self._count(MLModel)

    async def count_tasks(self, *, task_type: str | None = None) -> int:
        conditions = [Task.task_type == task_type] if task_type else []
        return await self._count(Task, conditions)

    async def count_running_tasks(self) -> int:
        return await self._count(Task, [Task.status == "running"])

    async def count_reviews(self, status: str | None = None) -> int:
        conditions = [AnnotationReview.status == status] if status else []
        return await self._count(AnnotationReview, conditions)

    async def recent_tasks(self, limit: int = 8) -> list[Task]:
        stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def task_stats(self, task_id: uuid.UUID) -> Task | None:
        return await self.session.get(Task, task_id)

    async def _count(self, model: type, conditions: list[object] | None = None) -> int:
        stmt = select(func.count()).select_from(model)
        if conditions:
            stmt = stmt.where(*conditions)
        return int((await self.session.execute(stmt)).scalar_one() or 0)
