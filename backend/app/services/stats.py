from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.stats import StatsRepository


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = StatsRepository(session)

    async def dashboard_overview(self) -> dict[str, Any]:
        return {
            "dataset_count": await self.repo.count_datasets(),
            "image_count": await self.repo.count_images(),
            "annotated_image_count": await self.repo.count_annotated_images(),
            "model_count": await self.repo.count_models(),
            "training_task_count": await self.repo.count_tasks(task_type="training"),
            "running_task_count": await self.repo.count_running_tasks(),
            "pending_review_count": await self.repo.count_reviews("pending"),
            "rejected_review_count": await self.repo.count_reviews("rejected"),
            "completed_review_count": await self.repo.count_reviews("approved"),
            "recent_tasks": await self.repo.recent_tasks(),
        }

    async def annotation_stats(self) -> dict[str, int]:
        return {
            "image_count": await self.repo.count_images(),
            "annotated_image_count": await self.repo.count_annotated_images(),
            "pending_review_count": await self.repo.count_reviews("pending"),
            "rejected_review_count": await self.repo.count_reviews("rejected"),
            "completed_review_count": await self.repo.count_reviews("approved"),
        }

    async def training_stats(self, task_id: uuid.UUID) -> dict[str, Any] | None:
        task = await self.repo.task_stats(task_id)
        if not task:
            return None
        return {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "result": task.result,
            "error_message": task.error_message,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        }
