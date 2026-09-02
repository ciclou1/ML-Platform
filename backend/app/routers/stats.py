# FastAPI dependencies use the established project router pattern.
# ruff: noqa: B008

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession
from app.exceptions import NotFoundError
from app.schemas.stats import AnnotationStatsResponse, DashboardOverviewResponse
from app.services.stats import StatsService

router = APIRouter(prefix="/stats", tags=["统计分析"])


def get_service(db: DbSession) -> StatsService:
    return StatsService(db)


@router.get("/overview", response_model=DashboardOverviewResponse, summary="查询概览统计")
async def overview(
    _: CurrentUser,
    service: StatsService = Depends(get_service),
):
    return await service.dashboard_overview()


@router.get("/annotations", response_model=AnnotationStatsResponse, summary="查询标注统计")
async def annotation_stats(
    _: CurrentUser,
    service: StatsService = Depends(get_service),
):
    return await service.annotation_stats()


@router.get("/training/{task_id}", summary="查询训练统计")
async def training_stats(
    task_id: uuid.UUID,
    _: CurrentUser,
    service: StatsService = Depends(get_service),
):
    result = await service.training_stats(task_id)
    if result is None:
        raise NotFoundError("Task not found")
    return result
