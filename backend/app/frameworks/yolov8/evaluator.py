import logging
from pathlib import Path
from typing import Any

from app.core.metric_entrypoint import run_metric_entrypoint
from app.core.metrics import add_custom_metrics
from app.core.storage.paths import StoragePaths
from app.frameworks.base import BaseEvaluator

logger = logging.getLogger(__name__)


class YOLOv8Evaluator(BaseEvaluator):
    async def evaluate(self, config: dict[str, Any]) -> dict[str, Any]:
        import torch
        from ultralytics import YOLO
        model_path = config["model_path"]
        device = config.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
        split = str(config.get("split", "val"))
        task_id = config.get("task_id", "standalone")

        model = YOLO(model_path)
        val_kwargs = self._build_val_kwargs(
            config, device=device, split=split, task_id=task_id
        )
        if getattr(model, "task", None) == "classify":
            val_kwargs["data"] = self._resolve_cls_data_dir(str(val_kwargs["data"]))
        results = model.val(**val_kwargs)

        metrics = self._extract_metrics(results, split=split)
        metrics = self._add_custom_metrics(metrics, results, config)

        logger.info("Evaluation completed: %s", metrics)
        return metrics

    def _build_val_kwargs(
        self,
        config: dict[str, Any],
        *,
        device: str,
        split: str,
        task_id: str,
    ) -> dict[str, Any]:
        val_kwargs: dict[str, Any] = {
            "data": config["data_yaml_path"],
            "split": split,
            "device": device,
            "imgsz": config.get("img_size", 640),
            "plots": True,
            "save_json": True,
            "exist_ok": True,
        }
        self._set_optional_val_kwargs(val_kwargs, config, task_id=task_id)
        return val_kwargs

    @staticmethod
    def _resolve_cls_data_dir(data: str) -> str:
        """ultralytics 分类任务要求数据参数为数据集根目录，而非 data.yaml 文件。"""

        path = Path(data)
        return str(path.parent) if path.is_file() else data

    def _add_custom_metrics(
        self,
        metrics: dict[str, Any],
        results: Any,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        metric_options = config.get("metric_options")
        options = metric_options if isinstance(metric_options, dict) else {}
        beta = self._safe_float(options.get("beta", 1.0))
        beta = beta if beta > 0 else 1.0
        weights = options.get("class_weights")
        class_weights = weights if isinstance(weights, dict) else None
        enriched = add_custom_metrics(
            metrics,
            per_class=metrics.get("per_class") or [],
            beta=beta,
            weights=class_weights,
        )
        predictions = self._extract_predictions(results)
        enriched["predictions"] = predictions

        entry_config = config.get("custom_metric_entrypoint")
        if isinstance(entry_config, dict):
            try:
                enriched["custom_metrics"] = run_metric_entrypoint(
                    entry_config,
                    {
                        "metrics": enriched,
                        "predictions": predictions,
                        "config": entry_config.get("config") or {},
                    },
                )
            except Exception as exc:  # Algorithm package code is an extension boundary.
                logger.warning("Custom metric entrypoint failed: %s", exc)
                enriched["custom_metrics_error"] = str(exc)
        return enriched

    def _extract_predictions(self, results: Any) -> list[dict[str, Any]]:
        raw_predictions = getattr(results, "jdict", None)
        if not isinstance(raw_predictions, list):
            return []
        return [item for item in raw_predictions if isinstance(item, dict)]

    def _set_optional_val_kwargs(
        self,
        val_kwargs: dict[str, Any],
        config: dict[str, Any],
        *,
        task_id: str,
    ) -> None:
        conf = config.get("conf")
        iou = config.get("iou")
        run_name = config.get("run_name", "eval")
        project_dir = config.get("project_dir", str(StoragePaths.run_root(task_id)))

        if conf is not None:
            val_kwargs["conf"] = conf
        if iou is not None:
            val_kwargs["iou"] = iou
        if project_dir:
            val_kwargs["project"] = project_dir
            val_kwargs["name"] = run_name

    def _extract_metrics(self, results: Any, *, split: str) -> dict[str, Any]:
        results_dict = getattr(results, "results_dict", {}) or {}
        keys = YOLOv8Evaluator._resolve_metric_keys(list(results_dict.keys()))
        precision = self._safe_float(results_dict.get(keys["precision"], 0))
        recall = self._safe_float(results_dict.get(keys["recall"], 0))
        map50 = self._safe_float(results_dict.get(keys["map50"], 0))
        map50_95 = self._safe_float(results_dict.get(keys["map50_95"], 0))
        map75 = self._safe_float(results_dict.get("metrics/mAP75(B)", 0))

        box_metrics = getattr(results, "box", None)
        speed = getattr(results, "speed", None)
        save_dir = getattr(results, "save_dir", None)

        per_class = self._extract_per_class_metrics(results, box_metrics)
        dataset_summary = self._extract_dataset_summary(results, box_metrics, per_class)

        return {
            "map50": map50,
            "map75": map75,
            "map50_95": map50_95,
            "precision": precision,
            "recall": recall,
            "f1": self._compute_f1(precision, recall),
            "fitness": self._safe_float(getattr(results, "fitness", 0)),
            "speed_ms": self._extract_speed(speed),
            "dataset_summary": dataset_summary,
            "per_class": per_class,
            "artifacts": self._extract_artifacts(save_dir),
            "evaluation_config": {
                "split": split,
            },
        }

    def _extract_per_class_metrics(self, results: Any, box_metrics: Any) -> list[dict[str, Any]]:
        if box_metrics is None:
            return []

        names = getattr(results, "names", {}) or {}
        ap_class_index = self._to_list(getattr(box_metrics, "ap_class_index", None))
        maps = self._to_list(getattr(box_metrics, "maps", None))
        nt_per_class = self._to_list(getattr(results, "nt_per_class", None))
        class_result = getattr(box_metrics, "class_result", None)

        rows: list[dict[str, Any]] = []
        for pos, class_idx in enumerate(ap_class_index):
            if not callable(class_result):
                break
            try:
                cls_precision, cls_recall, cls_map50, cls_map50_95 = class_result(pos)
            except Exception:
                continue

            class_id = int(class_idx)
            sample_count = 0
            if class_id < len(nt_per_class):
                sample_count = int(nt_per_class[class_id])

            rows.append(
                {
                    "class_id": class_id,
                    "class_name": str(names.get(class_id, class_id)),
                    "image_count": sample_count,
                    "precision": self._safe_float(cls_precision),
                    "recall": self._safe_float(cls_recall),
                    "f1": self._compute_f1(
                        self._safe_float(cls_precision),
                        self._safe_float(cls_recall),
                    ),
                    "map50": self._safe_float(cls_map50),
                    "map50_95": self._safe_float(cls_map50_95),
                    "map75": self._safe_float(maps[class_id]) if class_id < len(maps) else 0.0,
                }
            )

        rows.sort(key=lambda row: row["map50_95"], reverse=True)
        return rows

    def _extract_dataset_summary(
        self,
        results: Any,
        box_metrics: Any,
        per_class: list[dict[str, Any]],
    ) -> dict[str, Any]:
        names = getattr(results, "names", {}) or {}
        seen = self._resolve_evaluated_image_count(results, box_metrics)
        nt_per_class = self._to_list(getattr(results, "nt_per_class", None))
        target_instances = sum(int(v) for v in nt_per_class) if nt_per_class else 0
        evaluated_classes = len(per_class) or len(names)
        mp = self._safe_float(getattr(box_metrics, "mp", 0)) if box_metrics is not None else 0.0
        mr = self._safe_float(getattr(box_metrics, "mr", 0)) if box_metrics is not None else 0.0

        return {
            "images": seen,
            "instances": target_instances,
            "classes": evaluated_classes,
            "mean_precision": mp,
            "mean_recall": mr,
        }

    def _resolve_evaluated_image_count(self, results: Any, box_metrics: Any) -> int:
        if box_metrics is not None:
            image_metrics = getattr(box_metrics, "image_metrics", None)
            if isinstance(image_metrics, dict) and image_metrics:
                return len(image_metrics)

        try:
            seen = int(getattr(results, "seen", 0) or 0)
        except (TypeError, ValueError):
            return 0
        return seen if seen > 0 else 0

    def _extract_speed(self, speed: Any) -> dict[str, float]:
        if not isinstance(speed, dict):
            return {
                "preprocess": 0.0,
                "inference": 0.0,
                "loss": 0.0,
                "postprocess": 0.0,
                "total": 0.0,
            }

        preprocess = self._safe_float(speed.get("preprocess", 0))
        inference = self._safe_float(speed.get("inference", 0))
        loss = self._safe_float(speed.get("loss", 0))
        postprocess = self._safe_float(speed.get("postprocess", 0))
        total = preprocess + inference + loss + postprocess
        return {
            "preprocess": preprocess,
            "inference": inference,
            "loss": loss,
            "postprocess": postprocess,
            "total": total,
        }

    def _extract_artifacts(self, save_dir: Any) -> dict[str, str]:
        if save_dir is None:
            return {}

        base = Path(save_dir)
        artifact_names = [
            "confusion_matrix.png",
            "confusion_matrix_normalized.png",
            "BoxPR_curve.png",
            "BoxP_curve.png",
            "BoxR_curve.png",
            "BoxF1_curve.png",
        ]
        artifacts: dict[str, str] = {}
        for filename in artifact_names:
            path = base / filename
            if path.exists():
                artifacts[filename.rsplit(".", 1)[0]] = str(path)
        return artifacts

    def _compute_f1(self, precision: float, recall: float) -> float:
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _safe_float(self, value: Any) -> float:
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return 0.0

    def _to_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        try:
            return list(value)
        except TypeError:
            return [value]

    @staticmethod
    def _resolve_metric_keys(columns: list[str]) -> dict[str, str | None]:
        """按列名前缀模糊匹配指标列，兼容检测/分割/姿态/OBB/分类的列名后缀。"""

        normalized = {col.strip().lower(): col for col in columns}

        def find(prefix: str) -> str | None:
            matches = [orig for key, orig in normalized.items() if key.startswith(prefix)]
            return matches[0] if matches else None

        return {
            "map50": find("metrics/map50(") or find("metrics/accuracy_top1"),
            "map50_95": find("metrics/map50-95(") or find("metrics/accuracy_top5"),
            "precision": find("metrics/precision("),
            "recall": find("metrics/recall("),
        }
