"""远程节点与算法下发：注册、心跳、部署、远程推理请求与结果回传。

节点鉴权：注册时返回一次性 token，节点后续请求通过 X-Node-Token 头携带，
服务端比对 sha256(token) 与库中 token_hash。
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models.node import Node, NodeDeployment
from app.repositories.algorithm_package import AlgorithmPackageVersionRepository
from app.repositories.node import NodeDeploymentRepository, NodeRepository

import io
import json
import zipfile


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class NodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.node_repo = NodeRepository(session)
        self.deployment_repo = NodeDeploymentRepository(session)
        self.version_repo = AlgorithmPackageVersionRepository(session)

    async def list_nodes(self) -> list[Node]:
        return await self.node_repo.list(offset=0, limit=100)

    async def register(self, name: str) -> tuple[Node, str]:
        token = secrets.token_hex(32)
        node = await self.node_repo.create(
            Node(name=name, token_hash=_hash_token(token), status="offline")
        )
        return node, token

    async def authenticate(self, token: str) -> Node | None:
        return await self.node_repo.get_by_token_hash(_hash_token(token))

    async def heartbeat(self, node_id: uuid.UUID, token: str) -> Node | None:
        node = await self.node_repo.get_by_id(node_id)
        if not node or node.token_hash != _hash_token(token):
            return None
        node.status = "online"
        node.last_heartbeat = datetime.now(timezone.utc)
        return await self.node_repo.update(node)

    async def deploy(self, node_id: uuid.UUID, package_version_id: uuid.UUID) -> NodeDeployment:
        node = await self.node_repo.get_by_id(node_id)
        if not node:
            raise NotFoundError("Node not found")
        version = await self.version_repo.get_by_id(package_version_id)
        if not version:
            raise NotFoundError("Algorithm package version not found")
        return await self.deployment_repo.create(
            NodeDeployment(node_id=node_id, package_version_id=package_version_id)
        )

    async def undeploy(self, deployment_id: uuid.UUID) -> bool:
        deployment = await self.deployment_repo.get_by_id(deployment_id)
        if not deployment:
            return False
        await self.deployment_repo.delete(deployment)
        return True

    async def list_deployments(self, node_id: uuid.UUID) -> list[NodeDeployment]:
        return await self.deployment_repo.list_by_node(node_id)

    async def push_infer(self, deployment_id: uuid.UUID, params: dict[str, Any]) -> NodeDeployment | None:
        deployment = await self.deployment_repo.get_by_id(deployment_id)
        if not deployment:
            return None
        deployment.pending_params = params
        return await self.deployment_repo.update(deployment)

    async def post_results(
        self, deployment_id: uuid.UUID, output: dict[str, Any]
    ) -> NodeDeployment | None:
        deployment = await self.deployment_repo.get_by_id(deployment_id)
        if not deployment:
            return None
        deployment.last_result = output
        deployment.last_run_at = datetime.now(timezone.utc)
        deployment.pending_params = None
        return await self.deployment_repo.update(deployment)

    async def build_deployment_package(self, deployment_id: uuid.UUID) -> bytes | None:
        """生成节点可下载的算法包 zip（含 manifest + 推理代码 + 权重）。"""

        deployment = await self.deployment_repo.get_by_id(deployment_id)
        if not deployment:
            return None
        version = await self.version_repo.get_by_id(deployment.package_version_id)
        if not version:
            return None

        from app.core.storage.paths import StoragePaths

        root = StoragePaths.package_version_root(version.package_id, version.version)
        if not root.exists():
            return None

        manifest = {
            "deployment_id": str(deployment.id),
            "package_version_id": str(version.id),
            "version": version.version,
            "entrypoint": version.entrypoint,
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in root.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())
        return buffer.getvalue()
