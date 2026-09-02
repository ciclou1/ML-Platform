"""多类型标注形状校验与 YOLO 行转换单元测试。"""

from __future__ import annotations

import pytest

from app.core.annotation_shapes import (
    annotation_to_yolo_line,
    assert_exportable,
    infer_model_task,
    validate_annotation_data,
)
from app.exceptions import ValidationError


class TestValidateAnnotationData:
    def test_bbox_ok(self) -> None:
        validate_annotation_data("bbox", {"x": 10, "y": 20, "width": 30, "height": 40})

    def test_bbox_missing_field(self) -> None:
        with pytest.raises(ValidationError):
            validate_annotation_data("bbox", {"x": 10, "y": 20, "width": 30})

    def test_polygon_ok(self) -> None:
        validate_annotation_data("polygon", {"points": [[0, 0], [10, 0], [10, 10]]})

    def test_polygon_too_few_points(self) -> None:
        with pytest.raises(ValidationError):
            validate_annotation_data("polygon", {"points": [[0, 0], [10, 0]]})

    def test_obb_ok(self) -> None:
        validate_annotation_data("obb", {"cx": 5, "cy": 5, "w": 4, "h": 2, "angle": 0.3})

    def test_obb_bad_size(self) -> None:
        with pytest.raises(ValidationError):
            validate_annotation_data("obb", {"cx": 5, "cy": 5, "w": 0, "h": 2})

    def test_keypoint_ok(self) -> None:
        validate_annotation_data(
            "keypoint",
            {
                "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
                "points": [[1, 2, 2], [3, 4, 2]],
            },
        )

    def test_keypoint_missing_points(self) -> None:
        with pytest.raises(ValidationError):
            validate_annotation_data("keypoint", {"bbox": {"x": 0, "y": 0, "width": 1, "height": 1}})

    def test_classify_empty_data_ok(self) -> None:
        validate_annotation_data("classify", {})

    def test_unknown_type(self) -> None:
        with pytest.raises(ValidationError):
            validate_annotation_data("magic", {})


class TestYoloLineConversion:
    def test_bbox_line(self) -> None:
        line = annotation_to_yolo_line(
            "bbox", {"x": 0, "y": 0, "width": 50, "height": 100}, 3, 100, 200
        )
        assert line == "3 0.250000 0.250000 0.500000 0.500000"

    def test_polygon_line(self) -> None:
        line = annotation_to_yolo_line(
            "polygon", {"points": [[0, 0], [100, 0], [100, 100], [0, 100]]}, 0, 100, 100
        )
        assert line == "0 0.000000 0.000000 1.000000 0.000000 1.000000 1.000000 0.000000 1.000000"

    def test_obb_line_axis_aligned(self) -> None:
        # angle=0 时四个角即轴对齐框的四角
        line = annotation_to_yolo_line(
            "obb", {"cx": 50, "cy": 50, "w": 20, "h": 10, "angle": 0}, 1, 100, 100
        )
        parts = line.split()
        assert parts[0] == "1"
        assert len(parts) == 9  # class + 8 coords
        coords = [float(v) for v in parts[1:]]
        assert coords[0] == 0.6 and coords[1] == 0.55  # (60, 55)
        assert coords[4] == 0.4 and coords[5] == 0.45  # (40, 45)

    def test_keypoint_line(self) -> None:
        line = annotation_to_yolo_line(
            "keypoint",
            {
                "bbox": {"x": 0, "y": 0, "width": 100, "height": 100},
                "points": [[10, 20, 2], [30, 40, 1]],
            },
            2,
            100,
            100,
        )
        assert line.startswith("2 0.500000 0.500000 1.000000 1.000000")
        assert line.endswith("0.100000 0.200000 2 0.300000 0.400000 1")

    def test_classify_returns_none(self) -> None:
        assert annotation_to_yolo_line("classify", {}, 0, 100, 100) is None

    def test_zero_image_size_returns_none(self) -> None:
        assert annotation_to_yolo_line("bbox", {"x": 0, "y": 0, "width": 1, "height": 1}, 0, 0, 0) is None


class TestTaskInference:
    def test_priority_segment_first(self) -> None:
        assert infer_model_task(["bbox", "polygon"]) == "segment"

    def test_obb(self) -> None:
        assert infer_model_task(["obb"]) == "obb"

    def test_pose(self) -> None:
        assert infer_model_task(["keypoint"]) == "pose"

    def test_default_detect(self) -> None:
        assert infer_model_task([]) == "detect"


class TestExportGuard:
    def test_classify_only_is_exportable(self) -> None:
        assert_exportable(["classify"])

    def test_mixed_ok(self) -> None:
        assert_exportable(["classify", "bbox"])
        assert_exportable([])
