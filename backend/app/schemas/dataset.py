import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    data_type: str = "image"
    scene_category: str | None = None
    annotation_types: list[str] | None = None


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    scene_category: str | None = None
    annotation_types: list[str] | None = None


class DatasetResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    data_type: str
    storage_path: str | None
    scene_category: str | None
    annotation_types: list[Any] | None
    num_classes: int
    train_count: int
    val_count: int
    test_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImageResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    filename: str
    file_path: str
    width: int
    height: int
    split: str
    annotation_status: str
    video_id: uuid.UUID | None = None
    frame_index: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
