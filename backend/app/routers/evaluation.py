from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.evaluation import EvaluationRequest
from app.schemas.task import TaskResponse
from app.services.evaluation import EvaluationService
from app.services.task import TaskService

router = APIRouter(prefix="/evaluation", tags=["模型评估"])

@router.post("/run", response_model=TaskResponse, status_code=202, summary="发起模型评估任务")
async def run_evaluation(
    data: EvaluationRequest, db: AsyncSession = Depends(get_db)  # noqa: B008
):
    eval_service = EvaluationService(db)
    task_service = TaskService(db)
    task_data = await eval_service.build_task(
        data.model_id,
        data.dataset_id,
        algorithm_package_version_id=data.algorithm_package_version_id,
        config={
            "iou": data.iou_threshold,
            "metric_options": {
                "beta": data.fbeta_beta,
                "class_weights": data.class_weights or {},
            },
        },
    )
    task = await task_service.create_task(task_data)
    return await task_service.start_task(task.id)
