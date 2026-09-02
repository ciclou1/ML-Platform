from importlib.metadata import PackageNotFoundError, version as package_version

from fastapi import APIRouter

from app.config import settings
from app.deps import CurrentUser
from app.schemas.user import SystemConfigResponse

router = APIRouter(prefix="/system", tags=["系统管理"])


def _package_version(name: str) -> str:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return "--"


@router.get("/config", response_model=SystemConfigResponse, summary="查询系统配置（只读）")
async def get_system_config(_: CurrentUser):
    return SystemConfigResponse(
        app_name=settings.app_name,
        app_env=settings.app_env,
        storage_backend=settings.storage_backend,
        storage_root=str(settings.storage_path),
        max_upload_size_mb=settings.max_upload_size_mb,
        postgres_host=f"{settings.postgres_host}:{settings.postgres_port}",
        postgres_db=settings.postgres_db,
        versions={
            "ultralytics": _package_version("ultralytics"),
            "torch": _package_version("torch"),
            "fastapi": _package_version("fastapi"),
            "sqlalchemy": _package_version("sqlalchemy"),
        },
    )
