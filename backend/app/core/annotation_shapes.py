"""多类型标注的数据校验与 YOLO 标签行转换。

支持的标注类型（annotation.annotation_type）：
- bbox:      {"x", "y", "width", "height"}                       → YOLO detect 行
- polygon:   {"points": [[x, y], ...]}  (>=3 点)                 → YOLO seg 行
- obb:       {"cx", "cy", "w", "h", "angle"(弧度, 顺时针)}        → YOLO obb 行（8 坐标）
- keypoint:  {"bbox": {x,y,width,height}, "points": [[x,y,v],...]} → YOLO pose 行
- classify:  {}（图级标注，无几何）                                → YOLO-cls 目录结构，不产生几何行

所有坐标使用像素单位，转换时归一化。
"""

from __future__ import annotations

import math
from typing import Any

from app.exceptions import ValidationError

SUPPORTED_ANNOTATION_TYPES = ("bbox", "polygon", "obb", "keypoint", "classify")

# 训练任务类型（ultralytics task）：由数据集的标注类型推断
TASK_BY_ANNOTATION_PRIORITY = ("segment", "obb", "pose", "detect", "classify")
_TASK_BY_ANNOTATION_TYPE = {
    "polygon": "segment",
    "obb": "obb",
    "keypoint": "pose",
    "classify": "classify",
    "bbox": "detect",
}


def infer_model_task(annotation_types: list[str]) -> str:
    """根据数据集包含的标注类型推断 ultralytics 训练任务，无标注时为 detect。

    兼容直接传入任务名（detect/segment/obb/pose/classify）的情况。
    """

    present = set(annotation_types or [])
    for task in TASK_BY_ANNOTATION_PRIORITY:
        if task in present:
            return task
    mapped = {_TASK_BY_ANNOTATION_TYPE.get(str(item)) for item in present}
    for task in TASK_BY_ANNOTATION_PRIORITY:
        if task in mapped:
            return task
    return "detect"


def assert_exportable(annotation_types: list[str]) -> None:
    """Validate that only supported annotation types are exported."""

    unsupported = set(annotation_types or []) - set(SUPPORTED_ANNOTATION_TYPES)
    if unsupported:
        raise ValidationError(f"Unsupported annotation types: {', '.join(sorted(unsupported))}")


def validate_annotation_data(annotation_type: str, data: dict[str, Any]) -> None:
    """校验标注 data 与类型匹配，不合法时抛出 ValidationError。"""

    if annotation_type not in SUPPORTED_ANNOTATION_TYPES:
        raise ValidationError(
            f"不支持的标注类型: {annotation_type}，支持: {', '.join(SUPPORTED_ANNOTATION_TYPES)}"
        )
    if not isinstance(data, dict):
        raise ValidationError("标注数据格式无效，应为对象")

    if annotation_type == "bbox":
        _require_bbox(data, "bbox 标注缺少 x/y/width/height 字段")
    elif annotation_type == "polygon":
        points = _require_points(data, min_points=3)
        if len(points) < 3:
            raise ValidationError("多边形标注至少需要 3 个点")
    elif annotation_type == "obb":
        for key in ("cx", "cy", "w", "h"):
            if not _is_number(data.get(key)):
                raise ValidationError("旋转框标注缺少 cx/cy/w/h 数值字段")
        if _to_float(data.get("w")) <= 0 or _to_float(data.get("h")) <= 0:
            raise ValidationError("旋转框宽高必须为正数")
        if data.get("angle") is not None and not _is_number(data.get("angle")):
            raise ValidationError("旋转框角度必须为数值（弧度）")
    elif annotation_type == "keypoint":
        if "bbox" in data:
            _require_bbox(data["bbox"], "keypoint 标注的 bbox 字段无效")
        points = _require_points(data, min_points=1, key="points", with_visibility=True)
        if not points:
            raise ValidationError("keypoint 标注至少需要 1 个关键点")
    # classify: data 允许为空对象


def annotation_to_yolo_line(
    annotation_type: str,
    data: dict[str, Any],
    class_idx: int,
    img_w: int,
    img_h: int,
) -> str | None:
    """把单条标注转换为对应 YOLO 标签行；无几何（classify）返回 None。

    坐标越界时做裁剪（clamp 到图像范围），与原 bbox 行为保持一致。
    """

    if img_w <= 0 or img_h <= 0:
        return None

    if annotation_type == "bbox":
        return _bbox_line(class_idx, data, img_w, img_h)
    if annotation_type == "polygon":
        return _polygon_line(class_idx, data, img_w, img_h)
    if annotation_type == "obb":
        return _obb_line(class_idx, data, img_w, img_h)
    if annotation_type == "keypoint":
        return _keypoint_line(class_idx, data, img_w, img_h)
    return None


def translate_annotation_data(
    annotation_type: str, data: dict[str, Any], dx: float, dy: float
) -> dict[str, Any]:
    """Translate image-space annotation coordinates without changing its geometry."""

    translated = dict(data)
    if annotation_type == "bbox":
        translated["x"] = _to_float(data["x"]) + dx
        translated["y"] = _to_float(data["y"]) + dy
    elif annotation_type == "polygon":
        translated["points"] = [_translate_point(point, dx, dy) for point in data["points"]]
    elif annotation_type == "obb":
        translated["cx"] = _to_float(data["cx"]) + dx
        translated["cy"] = _to_float(data["cy"]) + dy
    elif annotation_type == "keypoint":
        translated["points"] = [_translate_point(point, dx, dy) for point in data["points"]]
        bbox = data.get("bbox")
        if isinstance(bbox, dict):
            translated["bbox"] = translate_annotation_data("bbox", bbox, dx, dy)
    return translated


def _translate_point(point: Any, dx: float, dy: float) -> list[Any]:
    translated = list(point)
    translated[0] = _to_float(translated[0]) + dx
    translated[1] = _to_float(translated[1]) + dy
    return translated


def _bbox_line(class_idx: int, data: dict[str, Any], img_w: int, img_h: int) -> str:
    x = _clamp(_to_float(data["x"]), img_w)
    y = _clamp(_to_float(data["y"]), img_h)
    width = _clamp(_to_float(data["width"]), img_w)
    height = _clamp(_to_float(data["height"]), img_h)
    cx = (x + width / 2) / img_w
    cy = (y + height / 2) / img_h
    return f"{class_idx} {cx:.6f} {cy:.6f} {width / img_w:.6f} {height / img_h:.6f}"


def _polygon_line(class_idx: int, data: dict[str, Any], img_w: int, img_h: int) -> str:
    coords: list[str] = []
    for point in data["points"]:
        px = _clamp(_to_float(point[0]), img_w)
        py = _clamp(_to_float(point[1]), img_h)
        coords.append(f"{px / img_w:.6f} {py / img_h:.6f}")
    return f"{class_idx} " + " ".join(coords)


def _obb_line(class_idx: int, data: dict[str, Any], img_w: int, img_h: int) -> str:
    cx = _to_float(data["cx"])
    cy = _to_float(data["cy"])
    w = _to_float(data["w"])
    h = _to_float(data["h"])
    angle = _to_float(data.get("angle") or 0.0)

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    # 中心角点偏移：四个角按 顺时针 从 (w/2, h/2) 起
    offsets = (
        (w / 2, h / 2),
        (-w / 2, h / 2),
        (-w / 2, -h / 2),
        (w / 2, -h / 2),
    )
    coords: list[str] = []
    for dx, dy in offsets:
        px = cx + dx * cos_a - dy * sin_a
        py = cy + dx * sin_a + dy * cos_a
        coords.append(f"{_clamp(px, img_w) / img_w:.6f} {_clamp(py, img_h) / img_h:.6f}")
    return f"{class_idx} " + " ".join(coords)


def _keypoint_line(class_idx: int, data: dict[str, Any], img_w: int, img_h: int) -> str:
    bbox = data.get("bbox") or {}
    base = _bbox_line(class_idx, bbox, img_w, img_h)

    kpt_coords: list[str] = []
    for point in data["points"]:
        px = _clamp(_to_float(point[0]), img_w)
        py = _clamp(_to_float(point[1]), img_h)
        v = int(_to_float(point[2])) if len(point) > 2 and _is_number(point[2]) else 2
        kpt_coords.append(f"{px / img_w:.6f} {py / img_h:.6f} {v}")
    return f"{base} " + " ".join(kpt_coords)


def _require_bbox(data: Any, message: str) -> None:
    if not isinstance(data, dict):
        raise ValidationError(message)
    for key in ("x", "y", "width", "height"):
        if not _is_number(data.get(key)):
            raise ValidationError(message)


def _require_points(
    data: dict[str, Any],
    *,
    min_points: int,
    key: str = "points",
    with_visibility: bool = False,
) -> list[Any]:
    points = data.get(key)
    if not isinstance(points, list) or len(points) < min_points:
        return []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValidationError("坐标点格式无效，应为 [x, y]")
        if not _is_number(point[0]) or not _is_number(point[1]):
            raise ValidationError("坐标点格式无效，x/y 应为数值")
        if with_visibility and len(point) > 2 and not _is_number(point[2]):
            raise ValidationError("关键点可见性 v 应为数值")
    return points


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _to_float(value: Any) -> float:
    return float(value)


def _clamp(value: float, upper: float) -> float:
    return max(0.0, min(value, upper))
