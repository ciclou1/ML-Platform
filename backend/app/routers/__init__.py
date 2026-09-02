from fastapi import APIRouter

from app.routers.dataset import router as dataset_router
from app.routers.dataset_export import router as dataset_export_router
from app.routers.dataset_version import router as dataset_version_router
from app.routers.annotation import router as annotation_router
from app.routers.annotation_batch import batch_router as annotation_batch_router
from app.routers.annotation_batch import review_router as annotation_review_router
from app.routers.label import router as label_router
from app.routers.model import router as model_router
from app.routers.task import router as task_router
from app.routers.stats import router as stats_router
from app.routers.upload import router as upload_router
from app.routers.inference import router as inference_router
from app.routers.evaluation import router as evaluation_router
from app.routers.video import router as video_router
from app.routers.algorithm_package import router as algorithm_package_router
from app.routers.node import router as node_router
from app.routers.ws import router as ws_router
from app.routers.workflow import router as workflow_router
from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.routers.role import router as role_router
from app.routers.audit import router as audit_router
from app.routers.system_config import router as system_config_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(dataset_router)
api_router.include_router(dataset_version_router)
api_router.include_router(dataset_export_router)
api_router.include_router(annotation_router)
api_router.include_router(annotation_batch_router)
api_router.include_router(annotation_review_router)
api_router.include_router(label_router)
api_router.include_router(model_router)
api_router.include_router(task_router)
api_router.include_router(stats_router)
api_router.include_router(upload_router)
api_router.include_router(inference_router)
api_router.include_router(evaluation_router)
api_router.include_router(video_router)
api_router.include_router(algorithm_package_router)
api_router.include_router(node_router)
api_router.include_router(ws_router)
api_router.include_router(workflow_router)
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(role_router)
api_router.include_router(audit_router)
api_router.include_router(system_config_router)
