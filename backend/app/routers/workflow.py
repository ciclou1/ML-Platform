# ruff: noqa: B008

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.exceptions import NotFoundError
from app.schemas.task import TaskResponse
from app.schemas.workflow import WorkflowCreate, WorkflowResponse, WorkflowUpdate
from app.services.task import TaskService
from app.services.workflow import WorkflowService

router = APIRouter(prefix="/workflows", tags=["Workflow"])


def get_service(db: AsyncSession = Depends(get_db)) -> WorkflowService:
    return WorkflowService(db)


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(service: WorkflowService = Depends(get_service)):
    return await service.list_workflows()


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(data: WorkflowCreate, service: WorkflowService = Depends(get_service)):
    return await service.create(data)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID, data: WorkflowUpdate, service: WorkflowService = Depends(get_service)
):
    workflow = await service.update(workflow_id, data)
    if not workflow:
        raise NotFoundError("Workflow not found")
    return workflow


@router.post("/{workflow_id}/csv")
async def upload_workflow_csv(
    workflow_id: uuid.UUID,
    file: UploadFile = File(...),
    service: WorkflowService = Depends(get_service),
):
    try:
        return {
            "path": await service.upload_csv(workflow_id, file.filename or "input.csv", file.file)
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workflow_id}/run", response_model=TaskResponse, status_code=202)
async def run_workflow(workflow_id: uuid.UUID, csv_path: str, db: AsyncSession = Depends(get_db)):
    workflow_service = WorkflowService(db)
    task_service = TaskService(db)
    task = await workflow_service.create_run(workflow_id, csv_path)
    return await task_service.start_task(task.id)
