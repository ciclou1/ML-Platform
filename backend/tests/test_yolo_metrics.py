"""YOLO 指标解析纯逻辑测试：固定 results.csv 样例，锁定列解析行为。

M2 计划将列名后缀 (B/M/P) 改为映射表，本文件用于回归保护。
"""

from __future__ import annotations

from pathlib import Path

from app.frameworks.yolov8.evaluator import YOLOv8Evaluator
from app.frameworks.yolov8.trainer import YOLOv8Trainer


def write_results_csv(tmp_path: Path, header: list[str], rows: list[list[str]]) -> Path:
    csv_path = tmp_path / "results.csv"
    lines = [",".join(header), *(",".join(row) for row in rows)]
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path


class TestTrainerCsvMetrics:
    def test_picks_best_row_by_map50_95(self, tmp_path: Path) -> None:
        csv_path = write_results_csv(
            tmp_path,
            ["epoch", "metrics/mAP50(B)", "metrics/mAP50-95(B)", "metrics/precision(B)", "metrics/recall(B)"],
            [
                ["1", "0.5", "0.3", "0.6", "0.4"],
                ["2", "0.8", "0.6", "0.9", "0.7"],
                ["3", "0.7", "0.5", "0.8", "0.6"],
            ],
        )

        metrics = YOLOv8Trainer._read_best_metrics_from_csv(csv_path)

        assert metrics is not None
        assert metrics["best_epoch"] == 2
        assert metrics["map50"] == 0.8
        assert metrics["map50_95"] == 0.6
        assert metrics["precision"] == 0.9
        assert metrics["recall"] == 0.7

    def test_missing_score_columns_returns_none(self, tmp_path: Path) -> None:
        """列名完全缺失时返回 None，由调用方回退到 results 提取。"""

        csv_path = write_results_csv(tmp_path, ["epoch", "train/loss"], [["1", "0.5"]])

        assert YOLOv8Trainer._read_best_metrics_from_csv(csv_path) is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert YOLOv8Trainer._read_best_metrics_from_csv(tmp_path / "not_exist.csv") is None

    def test_empty_rows_returns_none(self, tmp_path: Path) -> None:
        csv_path = write_results_csv(
            tmp_path,
            ["epoch", "metrics/mAP50(B)", "metrics/mAP50-95(B)", "metrics/precision(B)", "metrics/recall(B)"],
            [],
        )

        assert YOLOv8Trainer._read_best_metrics_from_csv(csv_path) is None


class TestTrainerFormat:
    def test_format_parameter_count(self) -> None:
        assert YOLOv8Trainer._format_parameter_count(None) == "--"
        assert YOLOv8Trainer._format_parameter_count(0) == "--"
        assert YOLOv8Trainer._format_parameter_count(500) == "500"
        assert YOLOv8Trainer._format_parameter_count(3_200_000) == "3.20M"
        assert YOLOv8Trainer._format_parameter_count(1_500_000_000) == "1.50B"


class TestMetricKeyResolution:
    def test_detect_columns(self) -> None:
        keys = YOLOv8Trainer._resolve_metric_keys(
            ["epoch", "metrics/mAP50(B)", "metrics/mAP50-95(B)", "metrics/precision(B)", "metrics/recall(B)"]
        )
        assert keys["map50"] == "metrics/mAP50(B)"
        assert keys["map50_95"] == "metrics/mAP50-95(B)"
        assert keys["precision"] == "metrics/precision(B)"

    def test_segment_columns(self) -> None:
        keys = YOLOv8Trainer._resolve_metric_keys(
            ["metrics/mAP50(M)", "metrics/mAP50-95(M)", "metrics/precision(M)", "metrics/recall(M)"]
        )
        assert keys["map50"] == "metrics/mAP50(M)"
        assert keys["map50_95"] == "metrics/mAP50-95(M)"

    def test_classify_fallback(self) -> None:
        keys = YOLOv8Trainer._resolve_metric_keys(
            ["metrics/accuracy_top1", "metrics/accuracy_top5"]
        )
        assert keys["map50"] == "metrics/accuracy_top1"
        assert keys["map50_95"] == "metrics/accuracy_top5"

    def test_csv_best_row_with_segment_columns(self, tmp_path: Path) -> None:
        csv_path = write_results_csv(
            tmp_path,
            ["epoch", "metrics/mAP50(M)", "metrics/mAP50-95(M)", "metrics/precision(M)", "metrics/recall(M)"],
            [
                ["1", "0.4", "0.2", "0.5", "0.3"],
                ["2", "0.7", "0.5", "0.8", "0.6"],
            ],
        )

        metrics = YOLOv8Trainer._read_best_metrics_from_csv(csv_path)

        assert metrics is not None
        assert metrics["best_epoch"] == 2
        assert metrics["map50"] == 0.7
        assert metrics["map50_95"] == 0.5


class TestEvaluatorF1:
    def test_f1_basic(self) -> None:
        evaluator = YOLOv8Evaluator()
        assert evaluator._compute_f1(0.8, 0.6) == 2 * 0.8 * 0.6 / 1.4
        assert evaluator._compute_f1(0.0, 0.0) == 0.0

    def test_safe_float(self) -> None:
        evaluator = YOLOv8Evaluator()
        assert evaluator._safe_float("0.12345") == 0.1235
        assert evaluator._safe_float("bad") == 0.0
        assert evaluator._safe_float(None) == 0.0
