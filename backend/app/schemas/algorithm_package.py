import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AlgorithmPackageResponse(BaseModel):
    id: uuid.UUID
    name: str
    framework: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlgorithmPackageVersionResponse(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID
    version: str
    entrypoint: str
    runtime_config: dict[str, Any] | None
    weights_path: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
