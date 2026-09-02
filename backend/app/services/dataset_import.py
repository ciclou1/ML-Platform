import logging
import os
import zipfile
from pathlib import Path
from typing import Any

import yaml

from app.core.dataset_files import extract_class_names, read_image_size, read_yaml_payload
from app.core.storage.paths import StoragePaths

logger = logging.getLogger(__name__)

_IMAGE_EXTS = (".jpg", ".jpeg", ".png")
_DETECT_SPLITS = ("train", "valid", "val", "test")


class DatasetImporter:
    """Extract uploaded zip files and detect a YOLO-like dataset structure."""

    async def upload_and_extract(self, dataset_id: str, source) -> dict[str, Any]:
        upload_path = StoragePaths.upload_path(f"{dataset_id}.zip")
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with upload_path.open("wb") as file_obj:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                file_obj.write(chunk)
                total += len(chunk)
        try:
            self._extract_zip(dataset_id, upload_path)
        finally:
            upload_path.unlink(missing_ok=True)
        return {"status": "extracted", "size_bytes": total}

    def _extract_zip(self, dataset_id: str, zip_path: Path) -> Path:
        target = StoragePaths.dataset_root(dataset_id)
        target.mkdir(parents=True, exist_ok=True)
        resolved_target = target.resolve()

        with zipfile.ZipFile(zip_path, "r") as archive:
            archive_root = self._detect_archive_root(archive.infolist())
            for member in archive.infolist():
                relative_name = self._normalize_archive_member_name(
                    member.filename,
                    archive_root=archive_root,
                )
                if not relative_name:
                    continue

                member_path = target / relative_name
                resolved_path = member_path.resolve()
                if not str(resolved_path).startswith(str(resolved_target) + os.sep):
                    logger.warning("Skipping suspicious zip entry: %s", member.filename)
                    continue

                if member.is_dir():
                    resolved_path.mkdir(parents=True, exist_ok=True)
                    continue

                resolved_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, open(resolved_path, "wb") as dst:
                    dst.write(src.read())

        logger.info("Extracted dataset %s to %s", dataset_id, target)
        return target

    @staticmethod
    def _detect_archive_root(members: list[zipfile.ZipInfo]) -> str | None:
        root_names: set[str] = set()
        for member in members:
            normalized = member.filename.replace("\\", "/").lstrip("./")
            if not normalized:
                continue

            parts = [part for part in normalized.split("/") if part]
            if not parts:
                continue

            root_names.add(parts[0])
            if len(root_names) > 1:
                return None

        if len(root_names) != 1:
            return None

        root_name = next(iter(root_names))
        if not root_name.lower().endswith((".zip", ".yaml", ".yml")):
            return root_name
        return None

    @staticmethod
    def _normalize_archive_member_name(filename: str, *, archive_root: str | None) -> str:
        normalized = filename.replace("\\", "/").lstrip("./")
        if not normalized:
            return ""

        if archive_root:
            prefix = f"{archive_root}/"
            if normalized == archive_root:
                return ""
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]

        return normalized

    def detect_structure(self, dataset_id: str) -> dict[str, Any]:
        root = StoragePaths.dataset_root(dataset_id)
        result: dict[str, Any] = {
            "root": str(root),
            "splits": self._detect_splits(root),
            "classes": [],
        }

        data_yaml = self._find_data_yaml(root)
        if data_yaml is not None:
            result["data_yaml_path"] = str(data_yaml)
            result["classes"] = self._parse_classes(data_yaml)

        if not result["classes"]:
            result["classes"] = self._detect_classes_without_yaml(root)

        return result

    def generate_data_yaml(self, dataset_id: str, classes: list[str]) -> str:
        root = StoragePaths.dataset_root(dataset_id)
        yaml_path = StoragePaths.dataset_yaml(dataset_id)

        if not classes:
            classes = self._scan_classes_from_labels(root)
        if not classes:
            classes = self._scan_classes_from_split_class_dirs(root)

        data: dict[str, Any] = {
            "path": str(root),
            "names": dict(enumerate(classes)),
            "nc": len(classes),
        }

        split_aliases = {
            "train": ("train",),
            "val": ("val", "valid"),
            "test": ("test",),
        }
        for split_name, candidates in split_aliases.items():
            images_dir = next(
                (
                    found_dir
                    for candidate in candidates
                    if (found_dir := self._find_split_dir(root, candidate)) is not None
                ),
                None,
            )
            if images_dir is not None:
                data[split_name] = str(images_dir)

        # ultralytics 要求 yaml 同时含 train/val 键；缺失的划分回退到已有目录
        if "train" not in data and "val" in data:
            data["train"] = data["val"]
        if "val" not in data and "train" in data:
            data["val"] = data["train"]

        yaml_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        logger.info("Generated data.yaml at %s", yaml_path)
        return str(yaml_path)

    def list_images(self, dataset_id: str, split: str) -> list[dict[str, Any]]:
        root = StoragePaths.dataset_root(dataset_id)
        images_dir = self._find_split_dir(root, split)
        if images_dir is not None:
            return [
                self._build_image_entry(file_path)
                for file_path in sorted(images_dir.iterdir())
                if file_path.suffix.lower() in _IMAGE_EXTS
            ]

        return [
            self._build_image_entry(file_path)
            for file_path in sorted(root.rglob("*"))
            if file_path.suffix.lower() in _IMAGE_EXTS
        ]

    def _detect_splits(self, root: Path) -> dict[str, dict[str, Any]]:
        splits: dict[str, dict[str, Any]] = {}
        for split_name in _DETECT_SPLITS:
            images_dir = self._find_split_dir(root, split_name)
            if images_dir is None:
                continue

            image_count = self._count_images(images_dir)
            if image_count <= 0:
                continue

            splits[split_name] = {
                "images_dir": str(images_dir),
                "count": image_count,
            }

        if splits:
            return splits

        all_images = self._collect_images(root)
        if not all_images:
            return {}

        return {
            "train": {
                "images_dir": str(root),
                "count": len(all_images),
            }
        }

    def _detect_classes_without_yaml(self, root: Path) -> list[str]:
        class_dirs = self._scan_classes_from_image_dirs(root)
        if class_dirs:
            return class_dirs
        class_dirs = self._scan_classes_from_split_class_dirs(root)
        if class_dirs:
            return class_dirs
        return self._scan_classes_from_labels(root)

    def _scan_classes_from_image_dirs(self, root: Path) -> list[str]:
        class_dirs: list[str] = []
        for directory in root.iterdir():
            if not directory.is_dir():
                continue
            if directory.name in {"images", "labels"}:
                continue
            if any(file_path.suffix.lower() in _IMAGE_EXTS for file_path in directory.iterdir() if file_path.is_file()):
                class_dirs.append(directory.name)
        return sorted(class_dirs)

    def _scan_classes_from_split_class_dirs(self, root: Path) -> list[str]:
        """YOLO-cls 布局（train/<class>/images）：类别名取 split 目录下的子目录。"""

        for split_name in ("train", "val", "valid", "test"):
            split_dir = self._find_split_dir(root, split_name)
            if split_dir is None:
                continue
            classes = sorted(
                child.name
                for child in split_dir.iterdir()
                if child.is_dir()
                and any(
                    file_path.suffix.lower() in _IMAGE_EXTS
                    for file_path in child.iterdir()
                    if file_path.is_file()
                )
            )
            if classes:
                return classes
        return []

    def _collect_images(self, root: Path) -> list[Path]:
        return [file_path for file_path in root.rglob("*") if file_path.suffix.lower() in _IMAGE_EXTS]

    @classmethod
    def _build_image_entry(cls, path: Path) -> dict[str, Any]:
        width, height = cls._read_image_size(path)
        return {
            "filename": path.name,
            "path": str(path),
            "width": width,
            "height": height,
        }

    @staticmethod
    def _read_image_size(path: Path) -> tuple[int, int]:
        return read_image_size(path)

    @staticmethod
    def _count_images(images_dir: Path) -> int:
        return sum(1 for file_path in images_dir.iterdir() if file_path.suffix.lower() in _IMAGE_EXTS)

    @staticmethod
    def _find_data_yaml(root: Path) -> Path | None:
        preferred: list[Path] = []
        fallback: list[Path] = []

        for pattern in ("data.yaml", "data.yml"):
            preferred.extend(root.rglob(pattern))
        for pattern in ("*.yaml", "*.yml"):
            for candidate in root.rglob(pattern):
                if candidate not in preferred:
                    fallback.append(candidate)

        candidates = [*preferred, *fallback]
        for candidate in candidates:
            try:
                payload = read_yaml_payload(candidate)
            except Exception:
                continue

            class_names = extract_class_names(payload)
            has_split = any(
                isinstance(payload.get(key), str) and payload.get(key)
                for key in ("train", "val", "valid", "test")
            )
            if class_names and has_split:
                return candidate

        for candidate in candidates:
            if "names" in candidate.read_text(errors="ignore"):
                return candidate
        return None

    @staticmethod
    def _parse_classes(yaml_path: Path) -> list[str]:
        return extract_class_names(read_yaml_payload(yaml_path))

    @staticmethod
    def _find_split_dir(root: Path, split: str) -> Path | None:
        # 顶层候选兼容 YOLO-cls 布局（root/train/<class>/images）
        for direct in (root / "images" / split, root / split):
            if direct.is_dir():
                return direct

        return DatasetImporter._find_nested_split_dir(root, split)

    @staticmethod
    def _find_nested_split_dir(root: Path, split: str) -> Path | None:
        for images_dir in root.rglob("images"):
            if not images_dir.is_dir():
                continue
            candidate = images_dir / split
            if candidate.is_dir():
                return candidate

        for candidate in root.rglob(split):
            if candidate.is_dir() and candidate.parent.name == "images":
                return candidate

        for candidate in root.rglob(split):
            if not candidate.is_dir():
                continue
            nested_images_dir = candidate / "images"
            if nested_images_dir.is_dir():
                return nested_images_dir
        return None

    @staticmethod
    def _scan_classes_from_labels(root: Path) -> list[str]:
        class_ids: set[int] = set()
        for labels_dir in root.rglob("labels"):
            if not labels_dir.is_dir():
                continue
            for txt_file in labels_dir.rglob("*.txt"):
                for line in txt_file.read_text(errors="ignore").strip().splitlines():
                    parts = line.strip().split()
                    if not parts:
                        continue
                    try:
                        class_ids.add(int(parts[0]))
                    except ValueError:
                        continue

        if not class_ids:
            return []
        return [f"class_{index}" for index in range(max(class_ids) + 1)]
