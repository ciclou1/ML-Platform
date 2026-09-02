from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AnnotationBatchCreate(BaseModel):
    dataset_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    image_ids: list[uuid.UUID] = Field(min_length=1)
    assignee_user_id: uuid.UUID | None = None


class AnnotationBatchAction(BaseModel):
    """Reserved for future action metadata; actions intentionally accept an empty body."""


class AnnotationBatchItemResponse(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    image_id: uuid.UUID
    annotator_user_id: uuid.UUID | None
    status: str
    image_filename: str
    image_width: int
    image_height: int
    image_split: str
    created_at: datetime
    updated_at: datetime


class AnnotationBatchResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    description: str | None
    status: str
    assignee_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    total_count: int
    completed_count: int
    dataset_name: str | None = None
    assignee_name: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[AnnotationBatchItemResponse] = Field(default_factory=list)


class AnnotationReviewAction(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
    quality_score: float | None = Field(default=None, ge=0, le=100)


class AnnotationReviewResponse(BaseModel):
    id: uuid.UUID
    batch_item_id: uuid.UUID
    image_id: uuid.UUID
    annotator_user_id: uuid.UUID | None
    reviewer_user_id: uuid.UUID | None
    status: str
    quality_score: float | None
    comment: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    batch_id: uuid.UUID
    batch_name: str | None = None
    dataset_id: uuid.UUID | None = None
    dataset_name: str | None = None
    image_filename: str | None = None
    annotation_count: int = 0
    item_status: str | None = None
    annotator_name: str | None = None
    reviewer_name: str | None = None
