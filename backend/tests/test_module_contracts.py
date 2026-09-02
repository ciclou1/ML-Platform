"""Smoke contracts for every backend functional module.

These tests deliberately avoid external services. Behaviour-specific tests stay next to
their feature; this suite catches missing registration, mapping and module wiring.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

import pytest

from app.models.algorithm_package import AlgorithmPackage, AlgorithmPackageVersion
from app.models.annotation import Annotation
from app.models.annotation_batch import AnnotationBatch, AnnotationBatchItem, AnnotationReview
from app.models.base import Base
from app.models.dataset import Dataset, Image, Label
from app.models.dataset_version import DatasetExport, DatasetVersion
from app.models.model import MLModel
from app.models.node import Node, NodeDeployment
from app.models.task import Task, TaskStatus
from app.models.user import AuditLog, Role, User
from app.models.video import Video
from app.models.workflow import Workflow
from app.routers import api_router
from app.runners import (
    eval_worker,
    package_worker,
    preprocess_worker,
    train_worker,
    video_import_worker,
    workflow_worker,
)
from app.services.algorithm_package import AlgorithmPackageService
from app.services.annotation import AnnotationService
from app.services.annotation_batch import AnnotationBatchService
from app.services.annotation_export import AnnotationExportService
from app.services.audit import AuditService
from app.services.dataset import DatasetService
from app.services.dataset_import import DatasetImporter
from app.services.dataset_version import DatasetVersionService
from app.services.evaluation import EvaluationService
from app.services.inference import InferenceService
from app.services.label import LabelService
from app.services.model import MLModelService
from app.services.node import NodeService
from app.services.preset_alignment import PresetAlignmentService
from app.services.stats import StatsService
from app.services.task import _WORKER_MODULES, TaskService
from app.services.upload import UploadService
from app.services.user import RoleService, UserService
from app.services.video import VideoService
from app.services.workflow import WorkflowService
from scripts.seed_admin import BUILTIN_ROLES
from scripts.seed_equipment_templates import TEMPLATES


@pytest.mark.parametrize(
    ("model", "table_name", "required_columns"),
    [
        (Dataset, "datasets", {"name", "annotation_types", "status"}),
        (Label, "labels", {"dataset_id", "name", "skeleton"}),
        (Image, "images", {"dataset_id", "file_path", "video_id", "frame_index"}),
        (Annotation, "annotations", {"image_id", "label_id", "annotation_type", "data"}),
        (AnnotationBatch, "annotation_batches", {"dataset_id", "name", "status", "total_count"}),
        (AnnotationBatchItem, "annotation_batch_items", {"batch_id", "image_id", "status"}),
        (
            AnnotationReview,
            "annotation_reviews",
            {"batch_item_id", "image_id", "status", "comment"},
        ),
        (MLModel, "models", {"weight_path", "parent_model_id", "model_task", "metrics"}),
        (DatasetVersion, "dataset_versions", {"dataset_id", "split_config", "stats_snapshot"}),
        (DatasetExport, "dataset_exports", {"dataset_version_id", "data_yaml_path", "status"}),
        (Task, "tasks", {"task_type", "status", "config", "result"}),
        (AlgorithmPackage, "algorithm_packages", {"name", "framework", "status"}),
        (
            AlgorithmPackageVersion,
            "algorithm_package_versions",
            {"package_id", "entrypoint", "status"},
        ),
        (Node, "nodes", {"name", "token_hash", "last_heartbeat"}),
        (NodeDeployment, "node_deployments", {"node_id", "package_version_id", "last_result"}),
        (Video, "videos", {"dataset_id", "file_path", "frame_count"}),
        (Workflow, "workflows", {"name", "graph"}),
        (Role, "roles", {"name", "permissions", "is_builtin"}),
        (User, "users", {"username", "password_hash", "role_id", "status", "last_login_at"}),
        (AuditLog, "audit_logs", {"username", "method", "path", "status_code", "duration_ms"}),
    ],
)
def test_model_contracts(model: type[Base], table_name: str, required_columns: set[str]) -> None:
    table = Base.metadata.tables[table_name]

    assert model.__tablename__ == table_name
    assert {"id", "created_at", "updated_at"}.issubset(table.columns.keys())
    assert required_columns.issubset(table.columns.keys())


def test_task_status_contract() -> None:
    assert {status.value for status in TaskStatus} == {
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    }


@pytest.mark.parametrize(
    ("module_name", "expected_path"),
    [
        ("dataset", "/datasets"),
        ("dataset_version", "/dataset-versions"),
        ("dataset_export", "/dataset-exports"),
        ("annotation", "/annotations"),
        ("annotation_batch", "/annotation-batches"),
        ("label", "/labels"),
        ("model", "/models"),
        ("task", "/tasks"),
        ("stats", "/stats"),
        ("upload", "/upload"),
        ("inference", "/inference"),
        ("evaluation", "/evaluation"),
        ("video", "/videos"),
        ("algorithm_package", "/algorithm-packages"),
        ("node", "/nodes"),
        ("workflow", "/workflows"),
        ("ws", "/ws/tasks/{task_id}"),
        ("auth", "/auth"),
        ("user", "/users"),
        ("role", "/roles"),
        ("audit", "/audit-logs"),
        ("system_config", "/system"),
    ],
)
def test_router_module_has_expected_endpoint(module_name: str, expected_path: str) -> None:
    module = importlib.import_module(f"app.routers.{module_name}")
    paths = {route.path for route in module.router.routes}

    assert any(expected_path in path for path in paths)


def test_all_functional_routers_are_registered() -> None:
    paths = {route.path for route in api_router.routes}
    expected_prefixes = {
        "/api/v1/datasets",
        "/api/v1/models",
        "/api/v1/tasks",
        "/api/v1/evaluation",
        "/api/v1/videos",
        "/api/v1/algorithm-packages",
        "/api/v1/nodes",
        "/api/v1/workflows",
        "/api/v1/annotation-batches",
        "/api/v1/annotation-reviews",
        "/api/v1/ws/tasks/{task_id}",
    }

    for prefix in expected_prefixes:
        assert any(path.startswith(prefix) for path in paths)


@pytest.mark.parametrize(
    "service_factory",
    [
        lambda session: AlgorithmPackageService(session),
        lambda session: AnnotationService(session),
        lambda session: StatsService(session),
        lambda session: AnnotationBatchService(session),
        lambda session: AnnotationExportService(session),
        lambda session: DatasetService(session),
        lambda session: DatasetVersionService(session),
        lambda session: EvaluationService(session),
        lambda session: InferenceService(session),
        lambda session: LabelService(session),
        lambda session: MLModelService(session),
        lambda session: NodeService(session),
        lambda session: PresetAlignmentService(session),
        lambda session: TaskService(session),
        lambda session: UserService(session),
        lambda session: RoleService(session),
        lambda session: AuditService(session),
        lambda session: VideoService(session),
        lambda session: WorkflowService(session),
        lambda session: DatasetImporter(),
        lambda session: UploadService(),
    ],
    ids=[
        "algorithm_package",
        "annotation",
        "stats",
        "annotation_batch",
        "annotation_export",
        "dataset",
        "dataset_version",
        "evaluation",
        "inference",
        "label",
        "model",
        "node",
        "preset_alignment",
        "task",
        "user",
        "role",
        "audit",
        "video",
        "workflow",
        "dataset_import",
        "upload",
    ],
)
def test_service_module_constructs(service_factory: Callable[[object], object]) -> None:
    assert service_factory(object()) is not None


def test_worker_modules_expose_main_and_task_mapping() -> None:
    workers = (
        eval_worker,
        package_worker,
        preprocess_worker,
        train_worker,
        video_import_worker,
        workflow_worker,
    )

    assert all(callable(worker.main) for worker in workers)
    assert _WORKER_MODULES == {
        "training": "app.runners.train_worker",
        "evaluation": "app.runners.eval_worker",
        "video_import": "app.runners.video_import_worker",
        "preprocess": "app.runners.preprocess_worker",
        "package_inference": "app.runners.package_worker",
        "workflow": "app.runners.workflow_worker",
    }


def test_equipment_template_seed_contract() -> None:
    names = {template["name"] for template in TEMPLATES}

    assert names == {
        "generator-defect-detection",
        "turbine-inspection",
        "transformer-inspection",
    }
    assert all(template["labels"] for template in TEMPLATES)
    assert all(template["metrics_config"].get("pass_thresholds") for template in TEMPLATES)


def test_seed_admin_builtin_roles_contract() -> None:
    names = {name for name, _, _ in BUILTIN_ROLES}

    assert names == {"admin", "operator", "viewer"}
    permissions_by_role = {name: permissions for name, _, permissions in BUILTIN_ROLES}
    assert permissions_by_role["admin"] == ["*"]
    assert "system:manage" not in permissions_by_role["operator"]
    assert all(permission.endswith(":read") for permission in permissions_by_role["viewer"])
