import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.exceptions import NotFoundError
from app.schemas.node import (
    NodeDeployRequest,
    NodeDeploymentResponse,
    NodeRegisterRequest,
    NodeRegisterResponse,
    NodeResponse,
)
from app.services.node import NodeService

router = APIRouter(prefix="/nodes", tags=["边缘节点"])


def get_service(db: AsyncSession = Depends(get_db)) -> NodeService:
    return NodeService(db)


async def _require_node(
    db: AsyncSession = Depends(get_db),
    x_node_token: str | None = Header(default=None),
):
    if not x_node_token:
        raise HTTPException(status_code=401, detail="缺少 X-Node-Token 头")
    service = NodeService(db)
    node = await service.authenticate(x_node_token)
    if not node:
        raise HTTPException(status_code=401, detail="节点令牌无效")
    return node


@router.get("", response_model=list[NodeResponse], summary="查询节点列表")
async def list_nodes(service: NodeService = Depends(get_service)):
    return await service.list_nodes()


@router.post(
    "/register",
    response_model=NodeRegisterResponse,
    status_code=201,
    summary="注册远程节点（返回一次性令牌）",
)
async def register_node(
    data: NodeRegisterRequest, service: NodeService = Depends(get_service)
):
    node, token = await service.register(data.name)
    return NodeRegisterResponse(id=node.id, name=node.name, token=token)


@router.post("/{node_id}/heartbeat", summary="节点心跳")
async def heartbeat(
    node_id: uuid.UUID,
    x_node_token: str | None = Header(default=None),
    service: NodeService = Depends(get_service),
):
    if not x_node_token:
        raise HTTPException(status_code=401, detail="缺少 X-Node-Token 头")
    node = await service.heartbeat(node_id, x_node_token)
    if not node:
        raise HTTPException(status_code=401, detail="节点令牌无效")
    return {"status": "ok", "node_status": node.status}


@router.get("/me/deployments", summary="节点拉取已部署算法")
async def me_deployments(
    service: NodeService = Depends(get_service),
    node=Depends(_require_node),
):
    deployments = await service.list_deployments(node.id)
    return [
        {
            "deployment_id": str(dep.id),
            "package_version_id": str(dep.package_version_id),
            "status": dep.status,
        }
        for dep in deployments
    ]


@router.get(
    "/{node_id}/deployments",
    response_model=list[NodeDeploymentResponse],
    summary="查询节点部署记录",
)
async def list_deployments(
    node_id: uuid.UUID, service: NodeService = Depends(get_service)
):
    return await service.list_deployments(node_id)


@router.post(
    "/{node_id}/deploy",
    response_model=NodeDeploymentResponse,
    status_code=201,
    summary="部署算法包版本到节点",
)
async def deploy_package(
    node_id: uuid.UUID,
    data: NodeDeployRequest,
    service: NodeService = Depends(get_service),
):
    return await service.deploy(node_id, data.package_version_id)


@router.delete("/deployments/{deployment_id}", status_code=204, summary="取消节点部署")
async def undeploy(
    deployment_id: uuid.UUID, service: NodeService = Depends(get_service)
):
    deleted = await service.undeploy(deployment_id)
    if not deleted:
        raise NotFoundError("Deployment not found")


@router.post("/deployments/{deployment_id}/infer", summary="向节点下发远程推理请求")
async def push_infer(
    deployment_id: uuid.UUID,
    params: dict[str, Any] | None = None,
    service: NodeService = Depends(get_service),
):
    deployment = await service.push_infer(deployment_id, params or {})
    if not deployment:
        raise NotFoundError("Deployment not found")
    return {"status": "pending"}


# ===== 节点侧接口（X-Node-Token 鉴权）=====


@router.get("/deployments/{deployment_id}/package", summary="节点下载算法包")
async def deployment_package(
    deployment_id: uuid.UUID,
    service: NodeService = Depends(get_service),
    node=Depends(_require_node),
):
    content = await service.build_deployment_package(deployment_id)
    if content is None:
        raise NotFoundError("Deployment package not found")
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="deployment-{deployment_id}.zip"'},
    )


@router.get("/deployments/{deployment_id}/pending", summary="节点拉取待处理推理请求")
async def deployment_pending(
    deployment_id: uuid.UUID,
    service: NodeService = Depends(get_service),
    node=Depends(_require_node),
):
    deployments = await service.list_deployments(node.id)
    dep = next((d for d in deployments if str(d.id) == str(deployment_id)), None)
    if not dep:
        raise NotFoundError("Deployment not found")
    return {"pending": bool(dep.pending_params), "params": dep.pending_params or {}}


@router.post("/deployments/{deployment_id}/results", summary="节点回传推理结果")
async def deployment_results(
    deployment_id: uuid.UUID,
    output: dict[str, Any],
    service: NodeService = Depends(get_service),
    node=Depends(_require_node),
):
    deployment = await service.post_results(deployment_id, output)
    if not deployment:
        raise NotFoundError("Deployment not found")
    return {"status": "ok"}
