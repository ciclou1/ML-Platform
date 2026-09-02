from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, TaskStateError, ValidationError
from app.models.annotation import Annotation
from app.models.annotation_batch import AnnotationBatch, AnnotationBatchItem, AnnotationReview
from app.models.user import User
from app.repositories.annotation_batch import (
    AnnotationBatchItemRepository,
    AnnotationBatchRepository,
    AnnotationReviewRepository,
)
from app.repositories.dataset import DatasetRepository, ImageRepository
from app.repositories.user import UserRepository
from app.schemas.annotation_batch import AnnotationBatchCreate, AnnotationReviewAction


class AnnotationBatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_repo = AnnotationBatchRepository(session)
        self.item_repo = AnnotationBatchItemRepository(session)
        self.review_repo = AnnotationReviewRepository(session)
        self.dataset_repo = DatasetRepository(session)
        self.image_repo = ImageRepository(session)
        self.user_repo = UserRepository(session)

    async def list_batches(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        dataset_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = await self.batch_repo.list_filtered(
            offset=offset, limit=limit, dataset_id=dataset_id, status=status
        )
        return [self._batch_payload(row, include_items=False) for row in rows]

    async def get_batch(self, batch_id: uuid.UUID) -> dict[str, Any] | None:
        batch = await self.batch_repo.get_detail(batch_id)
        if not batch:
            return None
        await self._refresh_counts(batch)
        return self._batch_payload(batch, include_items=True)

    async def create_batch(self, data: AnnotationBatchCreate, creator: User) -> dict[str, Any]:
        dataset = await self.dataset_repo.get_by_id(data.dataset_id)
        if not dataset:
            raise NotFoundError("Dataset not found")

        if not data.name.strip():
            raise ValidationError("Batch name cannot be empty")
        if len(set(data.image_ids)) != len(data.image_ids):
            raise ValidationError("Duplicate image IDs are not allowed")
        image_ids = list(data.image_ids)
        images = await self.image_repo.list_by_ids(image_ids)
        if len(images) != len(image_ids):
            raise ValidationError("One or more images do not exist")
        if any(image.dataset_id != data.dataset_id for image in images):
            raise ValidationError("All images must belong to the selected dataset")

        assignee = None
        if data.assignee_user_id:
            assignee = await self.user_repo.get_by_id(data.assignee_user_id)
            if not assignee or assignee.status != "active":
                raise ValidationError("Assignee does not exist or is disabled")

        batch = AnnotationBatch(
            dataset_id=data.dataset_id,
            name=data.name.strip(),
            description=data.description,
            status="assigned" if assignee else "draft",
            assignee_user_id=assignee.id if assignee else None,
            created_by_user_id=creator.id,
            total_count=len(image_ids),
            completed_count=0,
        )
        await self.batch_repo.create(batch)
        self.session.add_all(
            [
                AnnotationBatchItem(
                    batch_id=batch.id,
                    image_id=image_id,
                    annotator_user_id=assignee.id if assignee else None,
                    status="pending",
                )
                for image_id in image_ids
            ]
        )
        await self.session.flush()
        detail = await self.batch_repo.get_detail(batch.id)
        if detail is None:  # pragma: no cover - the just-created row cannot disappear in-session
            raise NotFoundError("Annotation batch not found")
        return self._batch_payload(detail, include_items=True)

    async def start_batch(self, batch_id: uuid.UUID) -> dict[str, Any]:
        batch = await self.batch_repo.get_detail(batch_id)
        if not batch:
            raise NotFoundError("Annotation batch not found")
        if batch.status not in {"draft", "assigned", "in_progress"}:
            raise TaskStateError(f"Cannot start a batch in {batch.status} state")
        batch.status = "in_progress"
        for item in batch.items:
            if item.status == "pending" and batch.assignee_user_id:
                item.annotator_user_id = batch.assignee_user_id
        await self.batch_repo.update(batch)
        return self._batch_payload(batch, include_items=True)

    async def submit_batch(self, batch_id: uuid.UUID) -> dict[str, Any]:
        batch = await self.batch_repo.get_detail(batch_id)
        if not batch:
            raise NotFoundError("Annotation batch not found")
        if batch.status not in {"in_progress", "submitted"}:
            raise TaskStateError(f"Cannot submit a batch in {batch.status} state")
        if not batch.items:
            raise ValidationError("Cannot submit an empty annotation batch")

        for item in batch.items:
            if item.status != "approved":
                item.status = "submitted"
                review = await self.review_repo.get_pending_for_item(item.id)
                if review is None:
                    self.session.add(
                        AnnotationReview(
                            batch_item_id=item.id,
                            image_id=item.image_id,
                            annotator_user_id=item.annotator_user_id,
                            status="pending",
                        )
                    )
        batch.status = "submitted"
        await self.session.flush()
        await self._refresh_counts(batch)
        await self.batch_repo.update(batch)
        detail = await self.batch_repo.get_detail(batch.id)
        if detail is None:  # pragma: no cover
            raise NotFoundError("Annotation batch not found")
        return self._batch_payload(detail, include_items=True)

    async def cancel_batch(self, batch_id: uuid.UUID) -> dict[str, Any]:
        batch = await self.batch_repo.get_detail(batch_id)
        if not batch:
            raise NotFoundError("Annotation batch not found")
        if batch.status in {"completed", "cancelled"}:
            raise TaskStateError(f"Cannot cancel a batch in {batch.status} state")
        batch.status = "cancelled"
        await self.batch_repo.update(batch)
        return self._batch_payload(batch, include_items=True)

    async def list_items(self, batch_id: uuid.UUID) -> list[dict[str, Any]]:
        if not await self.batch_repo.get_by_id(batch_id):
            raise NotFoundError("Annotation batch not found")
        return [self._item_payload(item) for item in await self.item_repo.list_by_batch(batch_id)]

    async def list_reviews(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        batch_id: uuid.UUID | None = None,
        dataset_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        rows = await self.review_repo.list_filtered(
            offset=offset,
            limit=limit,
            status=status,
            batch_id=batch_id,
            dataset_id=dataset_id,
        )
        return [await self._review_payload(row) for row in rows]

    async def get_review(self, review_id: uuid.UUID) -> dict[str, Any] | None:
        review = await self.review_repo.get_detail(review_id)
        if not review:
            return None
        return await self._review_payload(review)

    async def approve_review(
        self, review_id: uuid.UUID, action: AnnotationReviewAction, reviewer: User
    ) -> dict[str, Any]:
        return await self._finish_review(review_id, action, reviewer, "approved")

    async def reject_review(
        self, review_id: uuid.UUID, action: AnnotationReviewAction, reviewer: User
    ) -> dict[str, Any]:
        if not (action.comment or "").strip():
            raise ValidationError("A rejection comment is required")
        return await self._finish_review(review_id, action, reviewer, "rejected")

    async def resubmit_review(self, review_id: uuid.UUID) -> dict[str, Any]:
        """Create a fresh pending review after an annotator fixes a rejected image."""
        review = await self.review_repo.get_detail(review_id)
        if not review:
            raise NotFoundError("Annotation review not found")
        if review.status != "rejected":
            raise ConflictError("Only rejected reviews can be submitted for re-review")

        item = review.batch_item
        batch = item.batch
        if batch.status == "cancelled":
            raise TaskStateError("Cannot resubmit a cancelled batch")
        if item.status not in {"rejected", "annotating"}:
            raise ConflictError(
                f"This image is no longer awaiting rework (current status: {item.status})"
            )
        if batch.status == "completed":
            batch.status = "in_progress"
        if item.status == "rejected":
            raise ValidationError("请先在标注工作台保存返工结果")
        if await self.review_repo.get_pending_for_item(item.id):
            raise ConflictError("This image already has a pending review")

        item.status = "submitted"
        if review.image:
            review.image.annotation_status = "annotated"
        batch.status = "submitted"
        new_review = AnnotationReview(
            batch_item_id=item.id,
            image_id=review.image_id,
            annotator_user_id=item.annotator_user_id or review.annotator_user_id,
            status="pending",
        )
        self.session.add(new_review)
        await self.item_repo.update(item)
        await self.batch_repo.update(batch)
        await self.session.flush()

        refreshed = await self.review_repo.get_detail(new_review.id)
        if not refreshed:  # pragma: no cover - the row was flushed in this transaction
            raise NotFoundError("Annotation review not found")
        return await self._review_payload(refreshed)

    async def _finish_review(
        self,
        review_id: uuid.UUID,
        action: AnnotationReviewAction,
        reviewer: User,
        status: str,
    ) -> dict[str, Any]:
        review = await self.review_repo.get_detail(review_id)
        if not review:
            raise NotFoundError("Annotation review not found")
        if review.status != "pending":
            raise ConflictError("This review has already been completed")
        review.status = status
        review.reviewer_user_id = reviewer.id
        review.quality_score = action.quality_score
        review.comment = action.comment.strip() if action.comment else None
        review.reviewed_at = datetime.now(UTC)

        item = review.batch_item
        batch = item.batch
        if batch.status == "cancelled":
            raise TaskStateError("Cannot review a cancelled batch")
        image = review.image
        item.status = status
        image.annotation_status = "approved" if status == "approved" else "rejected"
        if status == "rejected" and batch.status not in {"cancelled", "completed"}:
            batch.status = "in_progress"
        await self._refresh_counts(batch)
        if batch.total_count and batch.completed_count == batch.total_count:
            batch.status = "completed"
        await self.review_repo.update(review)
        await self.item_repo.update(item)
        await self.batch_repo.update(batch)
        return await self._review_payload(review)

    async def _refresh_counts(self, batch: AnnotationBatch) -> None:
        items = batch.items
        if not items:
            items = await self.item_repo.list_by_batch_for_update(batch.id)
        batch.total_count = len(items)
        batch.completed_count = sum(item.status == "approved" for item in items)

    @staticmethod
    def _item_payload(item: AnnotationBatchItem) -> dict[str, Any]:
        image = item.image
        return {
            "id": item.id,
            "batch_id": item.batch_id,
            "image_id": item.image_id,
            "annotator_user_id": item.annotator_user_id,
            "status": item.status,
            "image_filename": image.filename if image else "",
            "image_width": image.width if image else 0,
            "image_height": image.height if image else 0,
            "image_split": image.split if image else "",
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    @classmethod
    def _batch_payload(cls, batch: AnnotationBatch, *, include_items: bool) -> dict[str, Any]:
        return {
            "id": batch.id,
            "dataset_id": batch.dataset_id,
            "name": batch.name,
            "description": batch.description,
            "status": batch.status,
            "assignee_user_id": batch.assignee_user_id,
            "created_by_user_id": batch.created_by_user_id,
            "total_count": batch.total_count,
            "completed_count": batch.completed_count,
            "dataset_name": batch.dataset.name if batch.dataset else None,
            "assignee_name": cls._user_name(batch.assignee),
            "created_by_name": cls._user_name(batch.created_by),
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "items": [cls._item_payload(item) for item in batch.items] if include_items else [],
        }

    async def _review_payload(self, review: AnnotationReview) -> dict[str, Any]:
        item = review.batch_item
        batch = item.batch if item else None
        image = review.image
        count = 0
        if image:
            stmt = (
                select(func.count()).select_from(Annotation).where(Annotation.image_id == image.id)
            )
            count = int((await self.session.execute(stmt)).scalar_one() or 0)
        return {
            "id": review.id,
            "batch_item_id": review.batch_item_id,
            "image_id": review.image_id,
            "annotator_user_id": review.annotator_user_id,
            "reviewer_user_id": review.reviewer_user_id,
            "status": review.status,
            "quality_score": review.quality_score,
            "comment": review.comment,
            "reviewed_at": review.reviewed_at,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
            "batch_id": batch.id if batch else item.batch_id,
            "batch_name": batch.name if batch else None,
            "dataset_id": batch.dataset_id if batch else None,
            "dataset_name": batch.dataset.name if batch and batch.dataset else None,
            "image_filename": image.filename if image else None,
            "annotation_count": count,
            "item_status": item.status if item else None,
            "annotator_name": self._user_name(review.annotator),
            "reviewer_name": self._user_name(review.reviewer),
        }

    @staticmethod
    def _user_name(user: User | None) -> str | None:
        return (user.display_name or user.username) if user else None


# A descriptive alias keeps dependency names concise in routers and remains backwards compatible
# with callers that refer to the business concept as a review service.
AnnotationReviewService = AnnotationBatchService
