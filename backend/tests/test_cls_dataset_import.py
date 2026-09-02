"""YOLO-cls 布局导入与分类评估的数据路径修复测试。"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.core.storage.paths import StoragePaths
from app.frameworks.yolov8.evaluator import YOLOv8Evaluator
from app.services.dataset_import import DatasetImporter


def _make_cls_dataset(root: Path) -> Path:
    """构造 YOLO-cls 布局：root/train|val/<class>/images。"""

    for split in ("train", "val"):
        for cls_name, count in (("ants", 2), ("bees", 1)):
            class_dir = root / split / cls_name
            class_dir.mkdir(parents=True)
            for index in range(count):
                (class_dir / f"img{index}.jpg").write_bytes(b"fake")
    return root


class TestClsLayoutImport:
    def test_find_split_dir_detects_top_level_split(self, tmp_path: Path) -> None:
        _make_cls_dataset(tmp_path)

        assert DatasetImporter._find_split_dir(tmp_path, "train") == tmp_path / "train"
        assert DatasetImporter._find_split_dir(tmp_path, "val") == tmp_path / "val"

    def test_scan_classes_from_split_class_dirs(self, tmp_path: Path) -> None:
        _make_cls_dataset(tmp_path)

        assert DatasetImporter()._scan_classes_from_split_class_dirs(tmp_path) == [
            "ants",
            "bees",
        ]

    def test_generate_data_yaml_for_cls_layout(self, tmp_path: Path, monkeypatch) -> None:
        _make_cls_dataset(tmp_path)
        monkeypatch.setattr(
            StoragePaths, "dataset_root", staticmethod(lambda dataset_id: tmp_path)
        )

        yaml_path = DatasetImporter().generate_data_yaml("dataset-id", [])
        payload = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))

        assert payload["path"] == str(tmp_path)
        assert payload["names"] == {0: "ants", 1: "bees"}
        assert payload["nc"] == 2
        assert payload["train"] == str(tmp_path / "train")
        assert payload["val"] == str(tmp_path / "val")


class TestClsEvalDataPath:
    def test_yaml_file_resolves_to_parent_dir(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "data.yaml"
        yaml_file.write_text("path: .\n", encoding="utf-8")

        assert YOLOv8Evaluator._resolve_cls_data_dir(str(yaml_file)) == str(tmp_path)

    def test_directory_stays_unchanged(self, tmp_path: Path) -> None:
        assert YOLOv8Evaluator._resolve_cls_data_dir(str(tmp_path)) == str(tmp_path)


class TestMissingValFallback:
    def test_export_yaml_falls_back_to_train_when_val_missing(
        self, tmp_path: Path
    ) -> None:
        from app.services.annotation_export import AnnotationExportService

        (tmp_path / "images" / "train").mkdir(parents=True)
        (tmp_path / "images" / "train" / "a.jpg").write_bytes(b"fake")

        yaml_path = AnnotationExportService._write_data_yaml(tmp_path, ["蚂蚁"])
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        assert payload["val"] == "images/train"
        assert payload["names"] == {0: "蚂蚁"}
        assert "test" not in payload

    def test_export_yaml_keeps_val_when_present(self, tmp_path: Path) -> None:
        from app.services.annotation_export import AnnotationExportService

        for split in ("train", "val"):
            (tmp_path / "images" / split).mkdir(parents=True)
            (tmp_path / "images" / split / "a.jpg").write_bytes(b"fake")

        yaml_path = AnnotationExportService._write_data_yaml(tmp_path, ["cls"])
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        assert payload["val"] == "images/val"

    def test_import_yaml_falls_back_to_train_when_val_missing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "images" / "train").mkdir(parents=True)
        (tmp_path / "labels" / "train").mkdir(parents=True)
        (tmp_path / "images" / "train" / "a.jpg").write_bytes(b"fake")
        monkeypatch.setattr(
            StoragePaths, "dataset_root", staticmethod(lambda dataset_id: tmp_path)
        )

        yaml_path = Path(DatasetImporter().generate_data_yaml("dataset-id", []))
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        assert payload["val"] == payload["train"] == str(tmp_path / "images" / "train")
