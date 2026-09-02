from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.annotation_batch import AnnotationBatch, AnnotationBatchItem, AnnotationReview
from app.repositories.base import BaseRepository


class AnnotationBatchRepository(BaseRepository[AnnotationBatch]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnnotationBatch)

    async def list_filtered(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        dataset_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[AnnotationBatch]:
        stmt = (
            select(AnnotationBatch)
            .options(
                joinedload(AnnotationBatch.dataset),
                joinedload(AnnotationBatch.assignee),
                joinedload(AnnotationBatch.created_by),
            )
            .order_by(AnnotationBatch.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if dataset_id:
            stmt = stmt.where(AnnotationBatch.dataset_id == dataset_id)
        if status:
            stmt = stmt.where(AnnotationBatch.status == status)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_detail(self, batch_id: uuid.UUID) -> AnnotationBatch | None:
        stmt = (
            select(AnnotationBatch)
            .options(
                joinedload(AnnotationBatch.dataset),
                joinedload(AnnotationBatch.assignee),
                joinedload(AnnotationBatch.created_by),
                selectinload(AnnotationBatch.items).joinedload(AnnotationBatchItem.image),
                selectinload(AnnotationBatch.items).joinedload(AnnotationBatchItem.annotator),
            )
            .where(AnnotationBatch.id == batch_id)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()


class AnnotationBatchItemRepository(BaseRepository[AnnotationBatchItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnnotationBatchItem)

    async def list_by_batch(self, batch_id: uuid.UUID) -> list[AnnotationBatchItem]:
        stmt = (
            select(AnnotationBatchItem)
            .options(
                joinedload(AnnotationBatchItem.image), joinedload(AnnotationBatchItem.annotator)
            )
            .where(AnnotationBatchItem.batch_id == batch_id)
            .order_by(AnnotationBatchItem.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_by_batch_for_update(self, batch_id: uuid.UUID) -> list[AnnotationBatchItem]:
        stmt = (
            select(AnnotationBatchItem)
            .where(AnnotationBatchItem.batch_id == batch_id)
            .order_by(AnnotationBatchItem.created_at)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_image(self, image_id: uuid.UUID) -> AnnotationBatchItem | None:
        stmt = (
            select(AnnotationBatchItem)
            .join(AnnotationBatchItem.batch)
            .where(
                AnnotationBatchItem.image_id == image_id,
                AnnotationBatch.status.not_in(("cancelled", "completed")),
            )
            .order_by(AnnotationBatchItem.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AnnotationReviewRepository(BaseRepository[AnnotationReview]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnnotationReview)

    async def list_filtered(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        batch_id: uuid.UUID | None = None,
        dataset_id: uuid.UUID | None = None,
    ) -> list[AnnotationReview]:
        stmt = (
            select(AnnotationReview)
            .join(AnnotationReview.batch_item)
            .join(AnnotationBatchItem.batch)
            .options(
                joinedload(AnnotationReview.image),
                joinedload(AnnotationReview.annotator),
                joinedload(AnnotationReview.reviewer),
                joinedload(AnnotationReview.batch_item)
                .joinedload(AnnotationBatchItem.batch)
                .joinedload(AnnotationBatch.dataset),
            )
            .order_by(AnnotationReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(AnnotationReview.status == status)
        if batch_id:
            stmt = stmt.where(AnnotationBatchItem.batch_id == batch_id)
        if dataset_id:
            stmt = stmt.where(AnnotationBatch.dataset_id == dataset_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_detail(self, review_id: uuid.UUID) -> AnnotationReview | None:
        stmt = (
            select(AnnotationReview)
            .options(
                joinedload(AnnotationReview.image),
                joinedload(AnnotationReview.annotator),
                joinedload(AnnotationReview.reviewer),
                joinedload(AnnotationReview.batch_item)
                .joinedload(AnnotationBatchItem.batch)
                .options(
                    joinedload(AnnotationBatch.dataset),
                    joinedload(AnnotationBatch.assignee),
                    selectinload(AnnotationBatch.items).joinedload(AnnotationBatchItem.image),
                ),
            )
            .where(AnnotationReview.id == review_id)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_pending_for_item(self, item_id: uuid.UUID) -> AnnotationReview | None:
        stmt = (
            select(AnnotationReview)
            .where(AnnotationReview.batch_item_id == item_id, AnnotationReview.status == "pending")
            .order_by(AnnotationReview.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
