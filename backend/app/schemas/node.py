import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NodeRegisterRequest(BaseModel):
    name: str


class NodeRegisterResponse(BaseModel):
    id: uuid.UUID
    name: str
    token: str


class NodeResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    last_heartbeat: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NodeDeployRequest(BaseModel):
    package_version_id: uuid.UUID


class NodeDeploymentResponse(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    package_version_id: uuid.UUID
    status: str
    pending_params: dict[str, Any] | None
    last_result: dict[str, Any] | None
    last_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
