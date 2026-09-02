"""storage/ 目录统一路径生成入口。

目录结构约定见 .claude/skills/storage-rules.md：

storage/
├─ datasets/{dataset_id}/
├─ exports/{export_id}/
├─ tasks/{task_id}/
├─ runs/{task_id}/
├─ models/{model_id}/
└─ uploads/
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import settings

EntityId = uuid.UUID | str | int


class StoragePaths:
    """所有 storage/ 路径统一通过本类生成，禁止业务代码手写路径拼接。"""

    @staticmethod
    def dataset_root(dataset_id: EntityId) -> Path:
        return settings.storage_path / "datasets" / str(dataset_id)

    @staticmethod
    def dataset_yaml(dataset_id: EntityId) -> Path:
        return StoragePaths.dataset_root(dataset_id) / "data.yaml"

    @staticmethod
    def export_root(export_id: EntityId) -> Path:
        return settings.storage_path / "exports" / str(export_id)

    @staticmethod
    def model_dir(model_id: EntityId) -> Path:
        return settings.storage_path / "models" / str(model_id)

    @staticmethod
    def video_path(video_id: EntityId, filename: str) -> Path:
        return settings.storage_path / "videos" / str(video_id) / filename

    @staticmethod
    def video_root(video_id: EntityId) -> Path:
        return settings.storage_path / "videos" / str(video_id)

    @staticmethod
    def package_root(package_id: EntityId) -> Path:
        return settings.storage_path / "packages" / str(package_id)

    @staticmethod
    def package_version_root(package_id: EntityId, version: str) -> Path:
        return settings.storage_path / "packages" / str(package_id) / version

    @staticmethod
    def workflow_root(workflow_id: EntityId) -> Path:
        return settings.storage_path / "workflows" / str(workflow_id)

    @staticmethod
    def workflow_csv(workflow_id: EntityId, filename: str) -> Path:
        return StoragePaths.workflow_root(workflow_id) / "inputs" / filename

    @staticmethod
    def upload_path(filename: str) -> Path:
        return settings.storage_path / "uploads" / filename

    @staticmethod
    def task_root(task_id: EntityId) -> Path:
        return settings.storage_path / "tasks" / str(task_id)

    @staticmethod
    def task_config(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "config.json"

    @staticmethod
    def task_pid(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "task.pid"

    @staticmethod
    def task_stdout(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "stdout.log"

    @staticmethod
    def task_stderr(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "stderr.log"

    @staticmethod
    def task_progress(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "progress.json"

    @staticmethod
    def task_result(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "result.json"

    @staticmethod
    def task_output_root(task_id: EntityId) -> Path:
        return StoragePaths.task_root(task_id) / "output"

    @staticmethod
    def task_output_file(task_id: EntityId, filename: str) -> Path:
        return StoragePaths.task_output_root(task_id) / filename

    @staticmethod
    def run_root(task_id: EntityId) -> Path:
        return settings.storage_path / "runs" / str(task_id)

    @staticmethod
    def task_run_dir(task_id: EntityId, run_name: str) -> Path:
        return StoragePaths.run_root(task_id) / run_name
