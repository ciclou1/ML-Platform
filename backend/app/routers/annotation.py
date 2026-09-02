import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.exceptions import NotFoundError
from app.schemas.annotation import (
    AnnotationBatchCreate,
    AnnotationCreate,
    AnnotationResponse,
    AnnotationUpdate,
)
from app.services.annotation import AnnotationService
from app.services.preset_alignment import PresetAlignmentService

router = APIRouter(tags=["标注管理"])


def get_service(db: AsyncSession = Depends(get_db)) -> AnnotationService:
    return AnnotationService(db)


def get_alignment_service(db: AsyncSession = Depends(get_db)) -> PresetAlignmentService:
    return PresetAlignmentService(db)


@router.get("/images/{image_id}/annotations", response_model=list[AnnotationResponse], summary="查询图片标注列表")
async def list_annotations(
    image_id: uuid.UUID, service: AnnotationService = Depends(get_service)
):
    return await service.list_by_image(image_id)


@router.post("/annotations", response_model=AnnotationResponse, status_code=201, summary="创建单条标注")
async def create_annotation(
    data: AnnotationCreate, service: AnnotationService = Depends(get_service)
):
    return await service.create_annotation(data)


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse, summary="更新标注")
async def update_annotation(
    annotation_id: uuid.UUID,
    data: AnnotationUpdate,
    service: AnnotationService = Depends(get_service),
):
    entity = await service.update_annotation(annotation_id, data)
    if not entity:
        raise NotFoundError("Annotation not found")
    return entity


@router.delete("/annotations/{annotation_id}", status_code=204, summary="删除标注")
async def delete_annotation(
    annotation_id: uuid.UUID, service: AnnotationService = Depends(get_service)
):
    deleted = await service.delete_annotation(annotation_id)
    if not deleted:
        raise NotFoundError("Annotation not found")


@router.post(
    "/images/{image_id}/annotations/batch",
    response_model=list[AnnotationResponse],
    status_code=201,
    summary="批量覆盖图片标注",
)
async def batch_create_annotations(
    image_id: uuid.UUID,
    data: AnnotationBatchCreate,
    service: AnnotationService = Depends(get_service),
):
    return await service.replace_for_image(image_id, data.annotations)


@router.post("/images/{image_id}/preset-alignment/estimate", summary="Estimate preset alignment shift")
async def estimate_preset_alignment(
    image_id: uuid.UUID,
    reference_image_id: uuid.UUID,
    service: PresetAlignmentService = Depends(get_alignment_service),
):
    return await service.estimate(image_id, reference_image_id)


@router.post("/images/{image_id}/preset-alignment/apply", summary="Correct annotations by preset shift")
async def apply_preset_alignment(
    image_id: uuid.UUID,
    reference_image_id: uuid.UUID,
    min_confidence: float = 0.0,
    service: PresetAlignmentService = Depends(get_alignment_service),
):
    return await service.apply(image_id, reference_image_id, min_confidence)
