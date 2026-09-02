import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage.paths import StoragePaths
from app.exceptions import NotFoundError
from app.models.algorithm_package import AlgorithmPackageVersion
from app.repositories.algorithm_package import AlgorithmPackageVersionRepository
from app.repositories.model import MLModelRepository
from app.schemas.task import TaskCreate

logger = logging.getLogger(__name__)


class EvaluationService:
    """Builds evaluation TaskCreate payloads. Routers call this then pass the
    payload to TaskService — services do not new other services.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.model_repo = MLModelRepository(session)
        self.version_repo = AlgorithmPackageVersionRepository(session)

    async def build_task(
        self,
        model_id: uuid.UUID,
        dataset_id: uuid.UUID,
        config: dict[str, Any] | None = None,
        algorithm_package_version_id: uuid.UUID | None = None,
    ) -> TaskCreate:
        model = await self.model_repo.get_by_id(model_id)
        if not model or not model.weight_path:
            raise NotFoundError(f"Model {model_id} not found or has no weights")

        task_config = {
            "model_path": model.weight_path,
            "model_id": str(model_id),
            "dataset_id": str(dataset_id),
            "framework": model.framework or "ultralytics",
            **(config or {}),
        }
        if algorithm_package_version_id:
            version = await self._get_published_metric_version(algorithm_package_version_id)
            runtime_config = version.runtime_config or {}
            task_config["custom_metric_entrypoint"] = {
                "package_root": str(
                    StoragePaths.package_version_root(version.package_id, version.version)
                ),
                "entrypoint": runtime_config["metrics_entrypoint"],
                "config": runtime_config.get("metrics_config") or {},
                "package_version_id": str(version.id),
            }

        return TaskCreate(
            name=f"Evaluate {model.name}",
            task_type="evaluation",
            model_id=model_id,
            dataset_id=dataset_id,
            config=task_config,
        )

    async def _get_published_metric_version(
        self, version_id: uuid.UUID
    ) -> AlgorithmPackageVersion:
        version = await self.version_repo.get_by_id(version_id)
        if not version or version.status != "published":
            raise NotFoundError("Published algorithm package version not found")
        runtime_config = version.runtime_config or {}
        entrypoint = runtime_config.get("metrics_entrypoint")
        if not isinstance(entrypoint, str) or not entrypoint:
            raise NotFoundError("Algorithm package version has no custom metric entrypoint")
        return version
