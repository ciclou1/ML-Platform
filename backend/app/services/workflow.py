from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage.factory import get_storage
from app.core.storage.paths import StoragePaths
from app.exceptions import NotFoundError, ValidationError
from app.models.task import Task
from app.models.workflow import Workflow
from app.repositories.task import TaskRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate


class WorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = WorkflowRepository(session)
        self.task_repo = TaskRepository(session)
        self.storage = get_storage()

    async def list_workflows(self) -> list[Workflow]:
        return await self.repo.list_all()

    async def create(self, data: WorkflowCreate) -> Workflow:
        self._validate_graph(data.graph)
        return await self.repo.create(
            Workflow(name=data.name, description=data.description, graph=data.graph)
        )

    async def update(self, workflow_id: uuid.UUID, data: WorkflowUpdate) -> Workflow | None:
        workflow = await self.repo.get_by_id(workflow_id)
        if not workflow:
            return None
        values = data.model_dump(exclude_unset=True)
        if "graph" in values:
            self._validate_graph(values["graph"])
        for key, value in values.items():
            setattr(workflow, key, value)
        return await self.repo.update(workflow)

    async def upload_csv(self, workflow_id: uuid.UUID, filename: str, source: BinaryIO) -> str:
        if not await self.repo.get_by_id(workflow_id):
            raise NotFoundError("Workflow not found")
        if not filename.lower().endswith(".csv"):
            raise ValidationError("Workflow input must be a CSV file")
        path = StoragePaths.workflow_csv(workflow_id, Path(filename).name)
        relative = str(path.relative_to(StoragePaths.workflow_root(workflow_id).parents[1]))
        await self.storage.save_stream(relative, source)
        return str(path)

    async def create_run(self, workflow_id: uuid.UUID, csv_path: str) -> Task:
        workflow = await self.repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError("Workflow not found")
        input_path = Path(csv_path)
        if not input_path.exists() or not input_path.is_file():
            raise ValidationError("Workflow CSV input does not exist")
        return await self.task_repo.create(
            Task(
                name=f"Workflow {workflow.name}",
                task_type="workflow",
                config={
                    "workflow_id": str(workflow.id),
                    "graph": workflow.graph,
                    "csv_path": str(input_path),
                },
            )
        )

    @staticmethod
    def _validate_graph(graph: dict[str, Any]) -> None:
        if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
            raise ValidationError("Workflow graph requires nodes and edges arrays")
