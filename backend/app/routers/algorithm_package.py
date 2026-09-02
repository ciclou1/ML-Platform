import uuid
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.exceptions import NotFoundError, ValidationError
from app.schemas.algorithm_package import (
    AlgorithmPackageResponse,
    AlgorithmPackageVersionResponse,
)
from app.schemas.task import TaskResponse
from app.services.algorithm_package import AlgorithmPackageService

router = APIRouter(prefix="/algorithm-packages", tags=["算法上架"])


def get_service(db: AsyncSession = Depends(get_db)) -> AlgorithmPackageService:
    return AlgorithmPackageService(db)


@router.get("", response_model=list[AlgorithmPackageResponse], summary="查询算法包列表")
async def list_packages(service: AlgorithmPackageService = Depends(get_service)):
    return await service.list_packages()


@router.get("/{package_id}", response_model=AlgorithmPackageResponse, summary="查询算法包详情")
async def get_package(
    package_id: uuid.UUID, service: AlgorithmPackageService = Depends(get_service)
):
    package = await service.get_package(package_id)
    if not package:
        raise NotFoundError("Algorithm package not found")
    return package


@router.post(
    "/import",
    response_model=AlgorithmPackageVersionResponse,
    status_code=201,
    summary="从 ZIP 导入算法包（含推理代码与可选权重）",
)
async def import_package(
    name: str = Form(...),
    version: str = Form(...),
    framework: str = Form("custom"),
    entrypoint: str = Form("inference.py:run"),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    service: AlgorithmPackageService = Depends(get_service),
):
    try:
        return await service.import_package(
            name=name,
            framework=framework,
            description=description,
            version=version,
            entrypoint=entrypoint,
            source=file.file,
        )
    except (ValueError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{package_id}/versions",
    response_model=list[AlgorithmPackageVersionResponse],
    summary="查询算法包版本列表",
)
async def list_versions(
    package_id: uuid.UUID, service: AlgorithmPackageService = Depends(get_service)
):
    return await service.list_versions(package_id)


@router.post(
    "/versions/{version_id}/publish",
    response_model=AlgorithmPackageVersionResponse,
    summary="发布算法包版本",
)
async def publish_version(
    version_id: uuid.UUID, service: AlgorithmPackageService = Depends(get_service)
):
    version = await service.publish_version(version_id)
    if not version:
        raise NotFoundError("Algorithm package version not found")
    return version


@router.post(
    "/versions/{version_id}/deprecate",
    response_model=AlgorithmPackageVersionResponse,
    summary="弃用算法包版本",
)
async def deprecate_version(
    version_id: uuid.UUID, service: AlgorithmPackageService = Depends(get_service)
):
    version = await service.deprecate_version(version_id)
    if not version:
        raise NotFoundError("Algorithm package version not found")
    return version


@router.get("/versions/{version_id}/download", summary="下载算法包版本（zip）")
async def download_version(
    version_id: uuid.UUID, service: AlgorithmPackageService = Depends(get_service)
):
    content = await service.build_download_zip(version_id)
    if content is None:
        raise NotFoundError("Algorithm package version not found")
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="package-{version_id}.zip"'},
    )


@router.post(
    "/versions/{version_id}/infer",
    response_model=TaskResponse,
    status_code=201,
    summary="本地运行算法包推理（创建任务）",
)
async def infer_version(
    version_id: uuid.UUID,
    params: dict[str, Any] | None = None,
    service: AlgorithmPackageService = Depends(get_service),
):
    return await service.create_inference_task(version_id, params)


@router.delete("/{package_id}", status_code=204, summary="删除算法包")
async def delete_package(
    package_id: uuid.UUID, service: AlgorithmPackageService = Depends(get_service)
):
    deleted = await service.delete_package(package_id)
    if not deleted:
        raise NotFoundError("Algorithm package not found")
