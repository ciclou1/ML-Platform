from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardTaskResponse(BaseModel):
    id: uuid.UUID
    name: str
    task_type: str
    status: str
    progress: int
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardOverviewResponse(BaseModel):
    dataset_count: int
    image_count: int
    annotated_image_count: int
    model_count: int
    training_task_count: int
    running_task_count: int
    pending_review_count: int
    rejected_review_count: int
    completed_review_count: int
    recent_tasks: list[DashboardTaskResponse]


class AnnotationStatsResponse(BaseModel):
    image_count: int
    annotated_image_count: int
    pending_review_count: int
    rejected_review_count: int
    completed_review_count: int
