"""Image preprocessing worker.

The worker is deliberately independent of the database.  The task config contains a
source-image manifest and the worker writes all outputs below ``storage/tasks/{id}/``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from app.core.storage.paths import StoragePaths

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _write_progress(task_id: str, done: int, total: int, **extra: Any) -> None:
    payload = {"progress": int(done / total * 100) if total else 100, "done": done, "total": total}
    payload.update(extra)
    StoragePaths.task_progress(task_id).write_text(json.dumps(payload), encoding="utf-8")


def _safe_name(filename: str, index: int, suffix: str = ".jpg") -> str:
    stem = Path(filename).stem.replace(" ", "_") or "image"
    return f"{index:06d}_{stem}{suffix}"


def _split_name(index: int, total: int, ratios: dict[str, float]) -> str:
    train_end = total * ratios["train"]
    val_end = train_end + total * ratios["val"]
    if index < train_end:
        return "train"
    if index < val_end:
        return "val"
    return "test"


def _save_image(image: Image.Image, target: Path, output_format: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "png":
        image.save(target, format="PNG")
    else:
        image.convert("RGB").save(target, format="JPEG", quality=95)


def _normalise_ratios(config: dict[str, Any]) -> dict[str, float]:
    raw = config.get("split_ratios") or {}
    values = {
        name: max(0.0, float(raw.get(name, default)))
        for name, default in (("train", 0.8), ("val", 0.1), ("test", 0.1))
    }
    total = sum(values.values())
    if total <= 0:
        return {"train": 1.0, "val": 0.0, "test": 0.0}
    return {name: value / total for name, value in values.items()}


def _make_zip(output_root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in output_root.rglob("*"):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(output_root).as_posix())


def main() -> None:  # noqa: C901 - task worker keeps the file contract in one place
    if len(sys.argv) < 2:
        logger.error("Usage: python -m app.runners.preprocess_worker <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    config_path = StoragePaths.task_config(task_id)
    result_path = StoragePaths.task_result(task_id)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    StoragePaths.task_pid(task_id).write_text(str(os.getpid()), encoding="utf-8")
    output_root = StoragePaths.task_output_root(task_id)
    output_root.mkdir(parents=True, exist_ok=True)
    sources = list(config.get("source_images") or [])
    preprocess_type = str(config.get("preprocess_type") or "resize")
    output_format = str(config.get("output_format") or "jpg").lower()
    if output_format not in {"jpg", "png"}:
        output_format = "jpg"

    try:
        if not sources:
            raise ValueError("数据集没有可处理的图片")
        width = max(1, int(config.get("width") or 640))
        height = max(1, int(config.get("height") or 640))
        ratios = _normalise_ratios(config)
        files: list[dict[str, Any]] = []
        skipped = 0
        split_counts = {"train": 0, "val": 0, "test": 0}

        for index, source in enumerate(sources):
            source_path = Path(str(source.get("file_path") or ""))
            if not source_path.exists() or not source_path.is_file():
                skipped += 1
                _write_progress(task_id, index + 1, len(sources), skipped=skipped)
                continue
            try:
                with Image.open(source_path) as opened:
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                    if preprocess_type == "resize":
                        image = image.resize((width, height), Image.Resampling.LANCZOS)
                        outputs = [("images", image)]
                    elif preprocess_type == "augmentation":
                        enhanced = ImageEnhance.Contrast(image).enhance(1.1)
                        outputs = [("images", image), ("augmented", ImageOps.mirror(enhanced))]
                    elif preprocess_type == "format_convert":
                        outputs = [("images", image)]
                    elif preprocess_type == "split":
                        split = _split_name(index, len(sources), ratios)
                        outputs = [(split, image)]
                        split_counts[split] += 1
                    else:
                        raise ValueError(f"不支持的预处理类型: {preprocess_type}")

                    for group, output_image in outputs:
                        suffix = ".png" if output_format == "png" else ".jpg"
                        target = (
                            output_root
                            / group
                            / _safe_name(
                                str(source.get("filename") or source_path.name), index, suffix
                            )
                        )
                        _save_image(output_image, target, output_format)
                        files.append(
                            {
                                "source": str(source.get("filename") or source_path.name),
                                "path": str(target),
                                "group": group,
                            }
                        )
            except Exception as exc:
                skipped += 1
                logger.warning("Skipping %s: %s", source_path, exc)
            _write_progress(task_id, index + 1, len(sources), skipped=skipped)

        manifest_path = StoragePaths.task_output_file(task_id, "manifest.json")
        manifest_path.write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")
        zip_path = StoragePaths.task_output_file(task_id, "output.zip")
        _make_zip(output_root, zip_path)
        result_path.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "preprocess_type": preprocess_type,
                    "total_images": len(sources),
                    "processed_images": len(sources) - skipped,
                    "skipped_images": skipped,
                    "output_file_count": len(files),
                    "split_counts": split_counts,
                    "manifest_path": str(manifest_path),
                    "output_zip": str(zip_path),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _write_progress(task_id, len(sources), len(sources), skipped=skipped)
        logger.info("Preprocessing completed: %d outputs", len(files))
    except Exception as exc:
        result_path.write_text(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.exception("Preprocessing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
