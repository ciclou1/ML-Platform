# FastAPI declares dependencies in function defaults; this is the project-wide router pattern.
# ruff: noqa: B008

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.deps import CurrentUser, DbSession, require_permission
from app.exceptions import NotFoundError
from app.schemas.annotation_batch import (
    AnnotationBatchCreate,
    AnnotationBatchItemResponse,
    AnnotationBatchResponse,
    AnnotationReviewAction,
    AnnotationReviewResponse,
)
from app.services.annotation_batch import AnnotationBatchService

batch_router = APIRouter(prefix="/annotation-batches", tags=["标注批次"])
review_router = APIRouter(prefix="/annotation-reviews", tags=["质检审核"])
# Keep the conventional module-level name used by router contract checks and integrations.
router = batch_router


def get_service(db: DbSession) -> AnnotationBatchService:
    return AnnotationBatchService(db)


@batch_router.get("", response_model=list[AnnotationBatchResponse], summary="查询标注批次")
async def list_batches(
    _: CurrentUser,
    dataset_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.list_batches(
        offset=(page - 1) * page_size,
        limit=page_size,
        dataset_id=dataset_id,
        status=status,
    )


@batch_router.post(
    "",
    response_model=AnnotationBatchResponse,
    status_code=201,
    summary="创建标注批次",
)
async def create_batch(
    data: AnnotationBatchCreate,
    user: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.create_batch(data, user)


@batch_router.get("/{batch_id}", response_model=AnnotationBatchResponse, summary="查询批次详情")
async def get_batch(
    batch_id: uuid.UUID,
    _: CurrentUser,
    service: AnnotationBatchService = Depends(get_service),
):
    result = await service.get_batch(batch_id)
    if result is None:
        raise NotFoundError("Annotation batch not found")
    return result


@batch_router.get(
    "/{batch_id}/items",
    response_model=list[AnnotationBatchItemResponse],
    summary="查询批次图片",
)
async def list_batch_items(
    batch_id: uuid.UUID,
    _: CurrentUser,
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.list_items(batch_id)


@batch_router.post(
    "/{batch_id}/start", response_model=AnnotationBatchResponse, summary="启动标注批次"
)
async def start_batch(
    batch_id: uuid.UUID,
    _: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.start_batch(batch_id)


@batch_router.post(
    "/{batch_id}/submit", response_model=AnnotationBatchResponse, summary="提交批次质检"
)
async def submit_batch(
    batch_id: uuid.UUID,
    _: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.submit_batch(batch_id)


@batch_router.post(
    "/{batch_id}/cancel", response_model=AnnotationBatchResponse, summary="取消标注批次"
)
async def cancel_batch(
    batch_id: uuid.UUID,
    _: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.cancel_batch(batch_id)


@review_router.get("", response_model=list[AnnotationReviewResponse], summary="查询质检审核记录")
async def list_reviews(
    _: CurrentUser,
    status: str | None = Query(None),
    batch_id: uuid.UUID | None = Query(None),
    dataset_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.list_reviews(
        offset=(page - 1) * page_size,
        limit=page_size,
        status=status,
        batch_id=batch_id,
        dataset_id=dataset_id,
    )


@review_router.get("/{review_id}", response_model=AnnotationReviewResponse, summary="查询审核详情")
async def get_review(
    review_id: uuid.UUID,
    _: CurrentUser,
    service: AnnotationBatchService = Depends(get_service),
):
    result = await service.get_review(review_id)
    if result is None:
        raise NotFoundError("Annotation review not found")
    return result


@review_router.post(
    "/{review_id}/approve",
    response_model=AnnotationReviewResponse,
    summary="审核通过",
)
async def approve_review(
    review_id: uuid.UUID,
    data: AnnotationReviewAction,
    user: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.approve_review(review_id, data, user)


@review_router.post(
    "/{review_id}/reject",
    response_model=AnnotationReviewResponse,
    summary="驳回审核",
)
async def reject_review(
    review_id: uuid.UUID,
    data: AnnotationReviewAction,
    user: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.reject_review(review_id, data, user)


@review_router.post(
    "/{review_id}/resubmit",
    response_model=AnnotationReviewResponse,
    summary="提交复审",
)
async def resubmit_review(
    review_id: uuid.UUID,
    _: Any = Depends(require_permission("annotation:write")),
    service: AnnotationBatchService = Depends(get_service),
):
    return await service.resubmit_review(review_id)
