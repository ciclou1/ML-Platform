"""设备算法模板启动包的生成物契约测试。

不依赖数据库：直接调用种子脚本的文件生成函数，把产物写入 tmp 目录，
再按平台真实加载路径（metric_entrypoint / importlib 子进程入口契约）执行验证。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.core.metric_entrypoint import run_metric_entrypoint
from scripts.seed_equipment_templates import (
    TEMPLATE_VERSION,
    TEMPLATES,
    _inference_code,
    _manifest,
    _metrics_code,
)


@pytest.fixture(params=TEMPLATES, ids=lambda template: template["name"])
def template(request: pytest.FixtureRequest) -> dict:
    return request.param


@pytest.fixture
def package_dir(tmp_path: Path, template: dict) -> Path:
    root = tmp_path / template["name"] / TEMPLATE_VERSION
    root.mkdir(parents=True)
    (root / "inference.py").write_text(_inference_code(template), encoding="utf-8")
    (root / "metrics.py").write_text(_metrics_code(template), encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(_manifest(template), ensure_ascii=False), encoding="utf-8"
    )
    return root


def _load_entrypoint(module_path: Path, function_name: str):
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, function_name)


class TestInferenceEntrypoint:
    def test_no_weights_returns_structured_result(self, package_dir: Path) -> None:
        run = _load_entrypoint(package_dir / "inference.py", "run")

        output = run({"params": {}})

        assert output["status"] == "no_weights"
        assert "best.pt" in output["message"]
        assert output["labels"]

    def test_manifest_entrypoint_matches_contract(self, package_dir: Path) -> None:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))

        assert manifest["entrypoint"] == "inference.py:run"
        assert manifest["task"] == "detect"
        assert _load_entrypoint(package_dir / "inference.py", "run") is not None


class TestMetricsEntrypoint:
    def test_runs_through_platform_loader(self, package_dir: Path, template: dict) -> None:
        payload = {
            "metrics": {
                "per_class": [
                    {
                        "class_name": template["labels"][0],
                        "precision": 0.8,
                        "recall": 0.6,
                        "f1": 0.6857,
                        "map50": 0.7,
                    },
                    {
                        "class_name": "unknown_class",
                        "precision": 0.5,
                        "recall": 0.5,
                        "f1": 0.5,
                        "map50": 0.5,
                    },
                ],
            },
            "predictions": [],
            "config": template["metrics_config"],
        }

        output = run_metric_entrypoint(
            {"package_root": str(package_dir), "entrypoint": "metrics.py:run"}, payload
        )

        assert output["beta"] == template["metrics_config"]["beta"]
        assert output["weighted"]["precision"] > 0
        first_row = output["per_class"][0]
        assert first_row["weight"] == template["metrics_config"]["class_weights"][
            template["labels"][0]
        ]
        assert output["quality_checks"]
        assert isinstance(output["passed"], bool)

    def test_empty_metrics_does_not_raise(self, package_dir: Path) -> None:
        output = run_metric_entrypoint(
            {"package_root": str(package_dir), "entrypoint": "metrics.py:run"},
            {"metrics": {}, "predictions": [], "config": {}},
        )

        assert output["weighted"]["precision"] == 0.0
        assert output["passed"] is None
