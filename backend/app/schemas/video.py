import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VideoResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    filename: str
    fps: float | None
    duration_s: float | None
    frame_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoExtractRequest(BaseModel):
    frame_interval_seconds: int = Field(default=1, ge=1, le=600)
    split: str = Field(default="train", pattern="^(train|val|test)$")
