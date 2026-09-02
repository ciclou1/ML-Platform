"""算法包管理：ZIP 导入、版本管理、发布/弃用、下载打包。

包目录结构（storage/packages/{package_id}/{version}/）：
  manifest.json     元数据（input_schema / output_schema / params）
  inference.py      推理入口（或自定义 entrypoint 文件）
  weights/          权重文件（可选）

自研推理在子进程执行（app/runners/package_worker.py），单机可信环境。
"""

from __future__ import annotations

import io
import json
import os
import shutil
import uuid
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage.paths import StoragePaths
from app.exceptions import NotFoundError, ValidationError
from app.models.algorithm_package import AlgorithmPackage, AlgorithmPackageVersion
from app.models.task import Task
from app.repositories.algorithm_package import (
    AlgorithmPackageRepository,
    AlgorithmPackageVersionRepository,
)
from app.repositories.task import TaskRepository

DEFAULT_ENTRYPOINT = "inference.py:run"


class AlgorithmPackageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.package_repo = AlgorithmPackageRepository(session)
        self.version_repo = AlgorithmPackageVersionRepository(session)
        self.task_repo = TaskRepository(session)

    async def list_packages(self, offset: int = 0, limit: int = 50) -> list[AlgorithmPackage]:
        return await self.package_repo.list(offset=offset, limit=limit)

    async def get_package(self, package_id: uuid.UUID) -> AlgorithmPackage | None:
        return await self.package_repo.get_by_id(package_id)

    async def list_versions(self, package_id: uuid.UUID) -> list[AlgorithmPackageVersion]:
        return await self.version_repo.list_by_package(package_id)

    async def import_package(
        self,
        *,
        name: str,
        framework: str,
        description: str | None,
        version: str,
        entrypoint: str,
        source,
    ) -> AlgorithmPackageVersion:
        """从 ZIP 导入算法包：ZIP 内含推理代码（必须）与 weights/（可选）。"""

        package = await self.package_repo.create(
            AlgorithmPackage(name=name, framework=framework, description=description)
        )

        root = StoragePaths.package_version_root(package.id, version)
        if root.exists():
            shutil.rmtree(root, True)
        root.mkdir(parents=True, exist_ok=True)
        resolved_root = root.resolve()

        with zipfile.ZipFile(source, "r") as archive:
            archive_root = self._detect_archive_root(archive.infolist())
            runtime_config = self._read_runtime_config(archive, archive_root)
            for member in archive.infolist():
                relative_name = self._normalize_member_name(member.filename, archive_root)
                if not relative_name:
                    continue
                member_path = root / relative_name
                resolved = member_path.resolve()
                if not str(resolved).startswith(str(resolved_root) + os.sep):
                    raise ValidationError(f"压缩包存在越界路径: {member.filename}")
                if member.is_dir():
                    resolved.mkdir(parents=True, exist_ok=True)
                else:
                    resolved.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as src, resolved.open("wb") as dst:
                        shutil.copyfileobj(src, dst)

        weights_dir = root / "weights"
        weights_path = str(weights_dir) if weights_dir.exists() else None

        entry_path = self._resolve_entrypoint_path(root, entrypoint)
        if not entry_path.exists():
            raise ValidationError(f"算法包缺少入口文件: {entrypoint}")
        metric_entrypoint = (runtime_config or {}).get("metrics_entrypoint")
        if isinstance(metric_entrypoint, str):
            metric_path = self._resolve_entrypoint_path(root, metric_entrypoint)
            if not metric_path.exists():
                raise ValidationError(f"算法包缺少自定义指标入口文件: {metric_entrypoint}")

        return await self.version_repo.create(
            AlgorithmPackageVersion(
                package_id=package.id,
                version=version,
                entrypoint=entrypoint or DEFAULT_ENTRYPOINT,
                runtime_config=runtime_config,
                weights_path=weights_path,
                status="draft",
            )
        )

    async def publish_version(self, version_id: uuid.UUID) -> AlgorithmPackageVersion | None:
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            return None
        version.status = "published"
        return await self.version_repo.update(version)

    async def deprecate_version(self, version_id: uuid.UUID) -> AlgorithmPackageVersion | None:
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            return None
        version.status = "deprecated"
        return await self.version_repo.update(version)

    async def delete_package(self, package_id: uuid.UUID) -> bool:
        package = await self.package_repo.get_by_id(package_id)
        if not package:
            return False
        root = StoragePaths.package_root(package_id)
        if root.exists():
            shutil.rmtree(root, True)
        await self.package_repo.delete(package)
        return True

    async def build_download_zip(self, version_id: uuid.UUID) -> bytes | None:
        """把算法包版本目录打成 zip（含 manifest、推理代码、权重）。"""

        version = await self.version_repo.get_by_id(version_id)
        if not version:
            return None
        root = StoragePaths.package_version_root(version.package_id, version.version)
        if not root.exists():
            return None

        manifest = {
            "package_version_id": str(version.id),
            "package_id": str(version.package_id),
            "version": version.version,
            "entrypoint": version.entrypoint,
            "runtime_config": version.runtime_config or {},
            "status": version.status,
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in root.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())
        return buffer.getvalue()

    async def create_inference_task(
        self, version_id: uuid.UUID, params: dict[str, Any] | None
    ) -> Task:
        """创建本地算法包推理任务（走任务系统子进程执行）。"""

        version = await self.version_repo.get_by_id(version_id)
        if not version:
            raise NotFoundError("Algorithm package version not found")

        config = {
            "package_root": str(
                StoragePaths.package_version_root(version.package_id, version.version)
            ),
            "entrypoint": version.entrypoint,
            "params": params or {},
        }
        task = Task(
            name=f"{version.version}-推理",
            task_type="package_inference",
            config=config,
        )
        return await self.task_repo.create(task)

    @staticmethod
    def _detect_archive_root(infos: list[zipfile.ZipInfo]) -> str:
        top_levels: set[str] = set()
        for info in infos:
            parts = [p for p in info.filename.split("/") if p]
            if parts:
                top_levels.add(parts[0])
        if len(top_levels) == 1 and not infos[0].is_dir() and all(
            info.filename.startswith(f"{next(iter(top_levels))}/") for info in infos
        ):
            return next(iter(top_levels))
        return ""

    @staticmethod
    def _normalize_member_name(filename: str, archive_root: str) -> str:
        if archive_root and filename.startswith(archive_root + "/"):
            return filename[len(archive_root) + 1:]
        if filename.startswith("/"):
            return ""
        return filename

    @staticmethod
    def _read_runtime_config(
        archive: zipfile.ZipFile, archive_root: str
    ) -> dict[str, Any] | None:
        manifest_name = next(
            (
                item.filename
                for item in archive.infolist()
                if AlgorithmPackageService._normalize_member_name(item.filename, archive_root)
                == "manifest.json"
            ),
            None,
        )
        if not manifest_name:
            return None

        try:
            manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Algorithm package manifest.json is invalid") from exc
        if not isinstance(manifest, Mapping):
            raise ValidationError("Algorithm package manifest.json must be an object")

        runtime = manifest.get("runtime_config")
        if runtime is not None and not isinstance(runtime, Mapping):
            raise ValidationError("manifest.runtime_config must be an object")
        runtime_config = dict(runtime or {})

        metrics = manifest.get("metrics")
        if metrics is not None and not isinstance(metrics, Mapping):
            raise ValidationError("manifest.metrics must be an object")
        metric_entrypoint = manifest.get("metrics_entrypoint") or (
            metrics.get("entrypoint") if isinstance(metrics, Mapping) else None
        )
        metric_config = manifest.get("metrics_config") or (
            metrics.get("config") if isinstance(metrics, Mapping) else None
        )
        if metric_entrypoint is not None:
            if not isinstance(metric_entrypoint, str) or not metric_entrypoint.strip():
                raise ValidationError("Custom metric entrypoint must be a non-empty string")
            runtime_config["metrics_entrypoint"] = metric_entrypoint
        if metric_config is not None:
            if not isinstance(metric_config, Mapping):
                raise ValidationError("Custom metric config must be an object")
            runtime_config["metrics_config"] = dict(metric_config)
        return runtime_config or None

    @staticmethod
    def _resolve_entrypoint_path(root: Path, entrypoint: str) -> Path:
        module_name, separator, function_name = entrypoint.partition(":")
        module_path = Path(module_name)
        if (
            not module_name
            or (separator and not function_name)
            or module_path.is_absolute()
            or ".." in module_path.parts
        ):
            raise ValidationError(f"Invalid algorithm package entrypoint: {entrypoint}")
        return root / module_path
