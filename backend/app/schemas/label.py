import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class LabelCreate(BaseModel):
    name: str
    color: str = "#FF0000"
    sort_order: int = 0
    skeleton: dict[str, Any] | None = None


class LabelUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    sort_order: int | None = None
    skeleton: dict[str, Any] | None = None


class LabelResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    color: str
    sort_order: int
    skeleton: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
