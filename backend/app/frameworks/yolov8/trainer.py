import json
import logging
import os
import time
from csv import DictReader
from pathlib import Path
from typing import Any

from app.core.storage.paths import StoragePaths
from app.frameworks.base import BaseTrainer

logger = logging.getLogger(__name__)


class YOLOv8Trainer(BaseTrainer):
    async def train(self, config: dict[str, Any]) -> dict[str, Any]:
        import torch
        from ultralytics import YOLO

        weight_path = config.get("weight_path")
        if not weight_path:
            raise ValueError("缺少 weight_path：训练任务必须指定本地预训练模型")
        task_id = config.get("task_id", "standalone")
        run_name = config.get("run_name", "train")
        project_dir = config.get("project_dir", str(StoragePaths.run_root(task_id)))
        model_task = config.get("model_task", "detect")
        metrics_suffix = {"segment": "M", "pose": "P"}.get(str(model_task), "B")
        progress_file = config.get("progress_file")
        resume_from = config.get("resume_from")
        if resume_from and not Path(resume_from).exists():
            raise ValueError(f"续训权重不存在: {resume_from}")
        workers = config.get("workers")
        if workers is None:
            # Windows multiprocessing can exhaust shared memory/pagefile during
            # large dataloader transfers, so default to single-process loading.
            workers = 0 if os.name == "nt" else 8

        device = config.get("device")
        if not device:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        if resume_from:
            # 断点续训：从 last.pt 恢复，ultralytics 沿用原任务的超参与运行目录
            model = YOLO(resume_from)
        else:
            model = YOLO(weight_path, task=model_task)
        history_file = (
            str(Path(progress_file).parent / "history.json")
            if progress_file
            else None
        )

        def _on_train_epoch_end(trainer_obj: Any) -> None:
            if not progress_file:
                return
            current = trainer_obj.epoch + 1
            total = trainer_obj.epochs
            progress = int((current / total) * 100)
            Path(progress_file).write_text(
                json.dumps({"progress": progress, "epoch": current, "total": total})
            )

            if history_file:
                epoch_data: dict[str, Any] = {"epoch": current}
                if trainer_obj.loss is not None:
                    epoch_data["train_loss"] = round(float(trainer_obj.loss.mean()), 4)
                if hasattr(trainer_obj, "metrics") and trainer_obj.metrics:
                    epoch_data["map50"] = round(
                        float(trainer_obj.metrics.get(f"metrics/mAP50({metrics_suffix})", 0)),
                        4,
                    )
                    epoch_data["map50_95"] = round(
                        float(
                            trainer_obj.metrics.get(f"metrics/mAP50-95({metrics_suffix})", 0)
                        ),
                        4,
                    )

                history_path = Path(history_file)
                history = (
                    json.loads(history_path.read_text())
                    if history_path.exists()
                    else []
                )
                history.append(epoch_data)
                history_path.write_text(
                    json.dumps(history, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        model.add_callback("on_train_epoch_end", _on_train_epoch_end)

        started_at = time.perf_counter()
        plots = bool(config.get("plots", False))
        if resume_from:
            results = model.train(
                resume=True,
                workers=workers,
                device=device,
                plots=plots,
            )
        else:
            results = model.train(
                data=config["data_yaml_path"],
                epochs=config.get("epochs", 50),
                batch=config.get("batch_size", 16),
                imgsz=config.get("img_size", 640),
                patience=config.get("patience", 10),
                optimizer=config.get("optimizer", "AdamW"),
                lr0=config.get("lr0", 0.01),
                warmup_epochs=config.get("warmup_epochs", 3),
                cos_lr=config.get("cos_lr", False),
                close_mosaic=config.get("close_mosaic", 10),
                freeze=config.get("freeze"),
                pretrained=config.get("pretrained", True),
                workers=workers,
                device=device,
                project=project_dir,
                name=run_name,
                exist_ok=True,
                plots=plots,
            )
        train_duration_seconds = time.perf_counter() - started_at

        # resume 时 ultralytics 会写回原任务的运行目录，优先取 trainer.save_dir
        trainer_save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
        run_dir = Path(trainer_save_dir) if trainer_save_dir else Path(project_dir) / run_name
        best_weight = run_dir / "weights" / "best.pt"
        results_csv = run_dir / "results.csv"
        metrics = (
            self._read_best_metrics_from_csv(results_csv)
            or self._extract_metrics(results)
        )
        metrics.update(
            {
                "weight_path": str(best_weight),
                "train_duration_seconds": round(train_duration_seconds, 2),
                "train_duration_minutes": round(train_duration_seconds / 60, 2),
                **self._read_model_summary(model, best_weight),
            }
        )

        logger.info("Training completed: %s", metrics)
        return metrics

    @staticmethod
    def _read_best_metrics_from_csv(results_csv: Path) -> dict[str, Any] | None:
        try:
            with results_csv.open("r", encoding="utf-8", newline="") as fp:
                rows = list(DictReader(fp))
        except OSError:
            return None

        if not rows:
            return None

        score_keys = YOLOv8Trainer._resolve_metric_keys(list(rows[0].keys()))
        best_row: dict[str, str] | None = None
        best_score: float | None = None

        score_key = score_keys["map50_95"] or score_keys["map50"]
        if not score_key:
            return None

        for row in rows:
            try:
                score = float(row.get(score_key, 0) or 0)
            except (TypeError, ValueError):
                continue
            if best_score is None or score > best_score:
                best_score = score
                best_row = row

        if not best_row:
            return None

        return {
            "best_epoch": YOLOv8Trainer._to_int(best_row.get("epoch")),
            "map50": YOLOv8Trainer._to_float(best_row.get(score_keys["map50"])),
            "map50_95": YOLOv8Trainer._to_float(best_row.get(score_keys["map50_95"])),
            "precision": YOLOv8Trainer._to_float(best_row.get(score_keys["precision"])),
            "recall": YOLOv8Trainer._to_float(best_row.get(score_keys["recall"])),
        }

    @staticmethod
    def _resolve_metric_keys(columns: list[str]) -> dict[str, str | None]:
        """按列名模糊匹配训练/评估指标列，兼容检测/分割/姿态/OBB/分类的列名后缀。

        ultralytics 的列后缀随任务类型变化：检测/OBB 为 (B)，分割为 (M)，姿态为 (P)。
        分类任务没有 mAP 列，用 accuracy_top1/top5 映射到 map50/map50_95。
        """

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

    @staticmethod
    def _read_model_summary(model: Any, best_weight: Path) -> dict[str, Any]:
        model_core = getattr(model, "model", None)
        parameter_count: int | None = None
        if model_core is not None and hasattr(model_core, "parameters"):
            try:
                parameter_count = sum(param.numel() for param in model_core.parameters())
            except (TypeError, ValueError):
                parameter_count = None

        weight_size_mb = 0.0
        if best_weight.exists():
            weight_size_mb = round(best_weight.stat().st_size / (1024 * 1024), 2)

        return {
            "parameter_count": parameter_count,
            "model_parameters": YOLOv8Trainer._format_parameter_count(parameter_count),
            "weight_size_mb": weight_size_mb,
        }

    @staticmethod
    def _format_parameter_count(parameter_count: int | None) -> str:
        if not parameter_count:
            return "--"
        if parameter_count >= 1_000_000_000:
            return f"{parameter_count / 1_000_000_000:.2f}B"
        if parameter_count >= 1_000_000:
            return f"{parameter_count / 1_000_000:.2f}M"
        if parameter_count >= 1_000:
            return f"{parameter_count / 1_000:.2f}K"
        return str(parameter_count)

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _extract_metrics(self, results: Any) -> dict[str, Any]:
        try:
            results_dict = results.results_dict
            keys = self._resolve_metric_keys(list(results_dict.keys()))
            return {
                "best_epoch": 0,
                "map50": float(results_dict.get(keys["map50"], 0)),
                "map50_95": float(results_dict.get(keys["map50_95"], 0)),
                "precision": float(results_dict.get(keys["precision"], 0)),
                "recall": float(results_dict.get(keys["recall"], 0)),
            }
        except (AttributeError, TypeError):
            return {
                "best_epoch": 0,
                "map50": 0,
                "map50_95": 0,
                "precision": 0,
                "recall": 0,
            }
