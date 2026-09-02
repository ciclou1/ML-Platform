import uuid
from typing import Any

from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    model_id: uuid.UUID
    dataset_id: uuid.UUID
    iou_threshold: float = Field(default=0.5, ge=0, le=1)
    algorithm_package_version_id: uuid.UUID | None = None
    fbeta_beta: float = Field(default=1.0, gt=0)
    class_weights: dict[str, float] | None = None


class EvaluationMetrics(BaseModel):
    map50: float
    map75: float | None = None
    map50_95: float
    precision: float
    recall: float
    f1: float | None = None
    fbeta: float | None = None
    weighted: dict[str, float] | None = None
    custom_metrics: dict[str, Any] | None = None
    custom_metrics_error: str | None = None
    fitness: float | None = None
    speed_ms: dict[str, float] | None = None
    dataset_summary: dict[str, Any] | None = None
    per_class: list[dict[str, Any]] | None = None
    artifacts: dict[str, str] | None = None
    evaluation_config: dict[str, Any] | None = None


class EvaluationResponse(BaseModel):
    task_id: uuid.UUID
    model_id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    metrics: EvaluationMetrics | None = None
