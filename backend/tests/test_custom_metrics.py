from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.core.metric_entrypoint import run_metric_entrypoint
from app.core.metrics import add_custom_metrics, aggregate_per_class_weighted, compute_fbeta
from app.services.algorithm_package import AlgorithmPackageService


def test_compute_fbeta_prioritizes_recall_when_beta_is_two() -> None:
    assert compute_fbeta(0.8, 0.5, beta=2) == 0.5405


def test_weighted_metrics_apply_class_weights() -> None:
    weighted = aggregate_per_class_weighted(
        [
            {"class_name": "critical", "precision": 0.8, "recall": 0.6, "map50": 0.7},
            {"class_name": "normal", "precision": 0.2, "recall": 0.4, "map50": 0.3},
        ],
        weights={"critical": 3, "normal": 1},
        beta=2,
    )

    assert weighted == {
        "weighted_precision": 0.65,
        "weighted_recall": 0.55,
        "weighted_fbeta": 0.5675,
        "weighted_map50": 0.6,
    }


def test_add_custom_metrics_adds_global_and_per_class_fbeta() -> None:
    result = add_custom_metrics(
        {"precision": 0.8, "recall": 0.5},
        per_class=[{"class_name": "defect", "precision": 0.6, "recall": 0.75, "map50": 0.7}],
        beta=2,
    )

    assert result["fbeta"] == 0.5405
    assert result["per_class"][0]["fbeta"] == 0.7143
    assert result["custom_config"] == {"beta": 2, "weights": {}}


def test_runs_custom_metric_entrypoint(tmp_path: Path) -> None:
    module_path = tmp_path / "metrics.py"
    module_path.write_text(
        "def evaluate(payload):\n"
        "    return {'alert_score': payload['metrics']['weighted']['weighted_recall']}\n",
        encoding="utf-8",
    )

    result = run_metric_entrypoint(
        {"package_root": str(tmp_path), "entrypoint": "metrics.py:evaluate"},
        {"metrics": {"weighted": {"weighted_recall": 0.75}}},
    )

    assert result == {"alert_score": 0.75}


def test_rejects_custom_metric_entrypoint_outside_package(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid custom metric entrypoint"):
        run_metric_entrypoint(
            {"package_root": str(tmp_path), "entrypoint": "../metrics.py:evaluate"},
            {},
        )


def test_manifest_metric_declaration_becomes_runtime_config(tmp_path: Path) -> None:
    archive_path = tmp_path / "package.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "manifest.json",
            '{"metrics": {"entrypoint": "metrics.py:evaluate", "config": {"level": 2}}}',
        )

    with zipfile.ZipFile(archive_path) as archive:
        runtime_config = AlgorithmPackageService._read_runtime_config(archive, "")

    assert runtime_config == {
        "metrics_entrypoint": "metrics.py:evaluate",
        "metrics_config": {"level": 2},
    }
