from typing import Any

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_permission
from app.schemas.user import AuditLogPage, AuditLogResponse
from app.services.audit import AuditService

router = APIRouter(prefix="/audit-logs", tags=["系统管理"])


def get_service(db: DbSession) -> AuditService:
    return AuditService(db)


@router.get("", response_model=AuditLogPage, summary="查询操作日志")
async def list_audit_logs(
    _: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    username: str | None = None,
    method: str | None = None,
    service: AuditService = Depends(get_service),
):
    rows, total = await service.search(
        offset=(page - 1) * page_size,
        limit=page_size,
        username=username or None,
        method=method or None,
    )
    return AuditLogPage(
        total=total,
        items=[AuditLogResponse.model_validate(row) for row in rows],
    )


@router.delete("", status_code=204, summary="清空操作日志")
async def clear_audit_logs(
    _: Any = Depends(require_permission("system:manage")),
    service: AuditService = Depends(get_service),
) -> None:
    await service.clear()
