"""Seed three domain algorithm-package starter kits after ``alembic upgrade head``.

每个模板生成一个可直接交付的算法启动包：

- inference.py          真实推理入口（Ultralytics YOLO，权重缺失时优雅降级）
- manifest.json         边缘节点 node_agent 依赖的包清单
- metrics.py            自定义评测指标入口（加权 F-beta + 达标阈值判定）
- README.md             类别体系、训练指引、推理契约与部署说明

训练权重由平台训练流程产生后放入包目录 ``weights/best.pt``。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 允许按 README 文档命令直接运行：uv run python scripts/seed_equipment_templates.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.storage.paths import StoragePaths
from app.db.postgres import async_session_factory
from app.models.algorithm_package import AlgorithmPackage, AlgorithmPackageVersion
from app.repositories.algorithm_package import (
    AlgorithmPackageRepository,
    AlgorithmPackageVersionRepository,
)

TEMPLATES = (
    {
        "name": "generator-defect-detection",
        "display_name": "发电机缺陷检测",
        "description": "Generator image defect detection; labels: oil_leak, corrosion, crack",
        "labels": ["oil_leak", "corrosion", "crack"],
        "train_defaults": {"model": "yolov8n.pt", "epochs": 100, "imgsz": 640, "batch": 16},
        "metrics_config": {
            "beta": 2.0,
            "class_weights": {"oil_leak": 1.5, "corrosion": 1.0, "crack": 1.2},
            "pass_thresholds": {"fbeta_weighted": 0.6, "recall_weighted": 0.7},
        },
    },
    {
        "name": "turbine-inspection",
        "display_name": "水轮机巡检",
        "description": "Hydro turbine inspection; labels: blade_damage, cavitation, foreign_object",
        "labels": ["blade_damage", "cavitation", "foreign_object"],
        "train_defaults": {"model": "yolov8s.pt", "epochs": 150, "imgsz": 960, "batch": 8},
        "metrics_config": {
            "beta": 1.0,
            "class_weights": {"blade_damage": 1.5, "cavitation": 1.0, "foreign_object": 1.0},
            "pass_thresholds": {"fbeta_weighted": 0.6, "precision_weighted": 0.7},
        },
    },
    {
        "name": "transformer-inspection",
        "display_name": "主变（变压器）巡检",
        "description": "Transformer image inspection; labels: hotspot, bushing_damage, oil_leak",
        "labels": ["hotspot", "bushing_damage", "oil_leak"],
        "train_defaults": {"model": "yolov8s.pt", "epochs": 120, "imgsz": 960, "batch": 8},
        "metrics_config": {
            "beta": 2.0,
            "class_weights": {"hotspot": 1.5, "bushing_damage": 1.2, "oil_leak": 1.0},
            "pass_thresholds": {"fbeta_weighted": 0.6, "recall_weighted": 0.7},
        },
    },
)

TEMPLATE_VERSION = "v1-template"

INFERENCE_TEMPLATE = '''"""{display_name} 推理入口。

包契约（由平台 package_worker / 边缘 node_agent 以子进程调用）：

- 入口：``run(payload) -> dict``，异常不应外抛，统一返回结构化结果
- 入参：``{{"params": {{"image": <图片路径或URL>, "conf": 0.25, "iou": 0.45, "imgsz": 640}}}}``
- 权重：包目录下 ``weights/best.pt``，由平台训练完成后复制进来
"""

from __future__ import annotations

import json
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
WEIGHTS_PATH = PACKAGE_ROOT / "weights" / "best.pt"
LABELS = {labels!r}


def run(payload: dict) -> dict:
    params = (payload or {{}}).get("params") or {{}}
    image = params.get("image")

    if not WEIGHTS_PATH.exists():
        return {{
            "status": "no_weights",
            "message": (
                "缺少 weights/best.pt，请先在平台完成训练并把 best.pt 复制到包 weights/ 目录"
            ),
            "labels": LABELS,
        }}
    if not image:
        return {{
            "status": "error",
            "message": "payload.params.image 不能为空（支持本地图片路径或 URL）",
            "labels": LABELS,
        }}

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        return {{
            "status": "error",
            "message": f"运行环境缺少 ultralytics: {{exc}}",
            "labels": LABELS,
        }}

    model = YOLO(str(WEIGHTS_PATH))
    predict_kwargs = {{
        key: params[key] for key in ("conf", "iou", "imgsz") if params.get(key) is not None
    }}
    results = model.predict(source=image, **predict_kwargs)

    detections = []
    for result in results:
        names = getattr(result, "names", {{}}) or {{}}
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            xyxy = [round(float(value), 2) for value in box.xyxy[0].tolist()]
            detections.append(
                {{
                    "label": names.get(int(box.cls[0]), str(int(box.cls[0]))),
                    "confidence": round(float(box.conf[0]), 4),
                    "bbox": {{"x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]}},
                }}
            )

    return {{
        "status": "ok",
        "model": WEIGHTS_PATH.name,
        "image": str(image),
        "detections": detections,
        "count": len(detections),
        "labels": LABELS,
    }}


if __name__ == "__main__":
    print(json.dumps(run({{"params": {{}}}}), ensure_ascii=False, indent=2))
'''

METRICS_TEMPLATE = '''"""{display_name} 自定义评测指标入口。

由评测服务通过 ``app.core.metric_entrypoint`` 加载执行，输出合并进评测结果
的 ``custom_metrics`` 字段。入参契约：

- ``metrics``:     平台汇总指标（含 ``per_class``：class_name/precision/recall/map50...）
- ``predictions``: 评测原始预测（本模板未使用，保留扩展位）
- ``config``:      包 ``runtime_config.metrics_config``（beta / class_weights / pass_thresholds）
"""

from __future__ import annotations


def run(payload: dict) -> dict:
    metrics = (payload or {{}}).get("metrics") or {{}}
    config = (payload or {{}}).get("config") or {{}}

    beta = float(config.get("beta", 1.0))
    class_weights = config.get("class_weights") or {{}}
    pass_thresholds = config.get("pass_thresholds") or {{}}

    rows = []
    total_weight = 0.0
    weighted_sum = {{"precision": 0.0, "recall": 0.0, "f1": 0.0, "map50": 0.0}}
    for row in metrics.get("per_class") or []:
        name = str(row.get("class_name") or row.get("name") or "")
        weight = float(class_weights.get(name, 1.0))
        precision = float(row.get("precision") or 0.0)
        recall = float(row.get("recall") or 0.0)
        rows.append(
            {{
                "class_name": name,
                "precision": precision,
                "recall": recall,
                "f1": float(row.get("f1") or 0.0),
                "map50": float(row.get("map50") or 0.0),
                "fbeta": _fbeta(precision, recall, beta),
                "weight": weight,
            }}
        )
        total_weight += weight
        weighted_sum["precision"] += precision * weight
        weighted_sum["recall"] += recall * weight
        weighted_sum["f1"] += float(row.get("f1") or 0.0) * weight
        weighted_sum["map50"] += float(row.get("map50") or 0.0) * weight

    if total_weight > 0:
        weighted = {{key: round(value / total_weight, 4) for key, value in weighted_sum.items()}}
    else:
        weighted = {{key: 0.0 for key in weighted_sum}}

    checks = {{
        key: {{
            "value": weighted.get(key, 0.0),
            "threshold": float(threshold),
            "passed": weighted.get(key, 0.0) >= float(threshold),
        }}
        for key, threshold in pass_thresholds.items()
    }}

    return {{
        "beta": beta,
        "weighted": weighted,
        "per_class": rows,
        "quality_checks": checks,
        "passed": all(item["passed"] for item in checks.values()) if checks else None,
    }}


def _fbeta(precision: float, recall: float, beta: float) -> float:
    denominator = beta * beta * precision + recall
    if denominator <= 0:
        return 0.0
    return round((1 + beta * beta) * precision * recall / denominator, 4)


if __name__ == "__main__":
    import json

    print(json.dumps(run({{"metrics": {{}}}}), ensure_ascii=False, indent=2))
'''


def _inference_code(template: dict) -> str:
    return INFERENCE_TEMPLATE.format(
        display_name=template["display_name"], labels=template["labels"]
    )


def _metrics_code(template: dict) -> str:
    return METRICS_TEMPLATE.format(display_name=template["display_name"])


def _manifest(template: dict) -> dict:
    return {
        "name": template["name"],
        "display_name": template["display_name"],
        "version": TEMPLATE_VERSION,
        "entrypoint": "inference.py:run",
        "task": "detect",
        "labels": template["labels"],
    }


def _readme(template: dict) -> str:
    defaults = template["train_defaults"]
    metrics_config = template["metrics_config"]
    label_lines = "\n".join(
        f"| {index + 1} | {name} |" for index, name in enumerate(template["labels"])
    )
    return f"""# {template['display_name']} 算法启动包

{template['description']}。本包为可直接交付的启动包：完成训练后把权重放入
``weights/best.pt`` 即可用于平台推理与边缘部署。

## 类别体系（detect 任务）

| 类别索引 | 类别名 |
| --- | --- |
{label_lines}

## 包结构

```text
inference.py      推理入口（entrypoint: inference.py:run）
metrics.py        自定义评测指标入口（metrics_entrypoint: metrics.py:run）
manifest.json     包清单（边缘 node_agent 依赖）
weights/best.pt   训练产物权重（训练完成后放入）
README.md         本文件
```

## 训练指引

1. 在"数据集管理"创建数据集并上传图片，标注上述类别（检测框）。
2. 在"数据集版本 / 导出记录"创建版本，按比例自动划分并完成 YOLO 导出（状态 success）。
3. 在"训练任务"选择该导出记录，推荐配置：
   - model: ``{defaults['model']}``
   - epochs: {defaults['epochs']}，imgsz: {defaults['imgsz']}，batch: {defaults['batch']}
4. 训练完成后从运行产物复制 ``best.pt`` 到本包版本的 ``weights/best.pt``。

## 推理契约

```json
{{"params": {{"image": "/path/to/image.jpg", "conf": 0.25, "iou": 0.45,
  "imgsz": {defaults['imgsz']}}}}}
```

返回 ``{{"status": "ok", "detections": [{{"label", "confidence", "bbox"}}], "count", "labels"}}``；
权重缺失时返回 ``{{"status": "no_weights"}}``，运行环境缺 ultralytics 时返回
``{{"status": "error"}}``，均不抛异常。

## 自定义评测指标

评测任务选择本包版本后，``metrics.py:run`` 会基于平台 per-class 指标计算加权
F-beta（beta={metrics_config['beta']}，类别权重 {metrics_config['class_weights']}），
并按 ``pass_thresholds``（{metrics_config['pass_thresholds']}）输出达标判定。
"""


async def seed() -> None:
    async with async_session_factory() as session:
        repo = AlgorithmPackageRepository(session)
        version_repo = AlgorithmPackageVersionRepository(session)
        for template in TEMPLATES:
            if await repo.get_by_name(template["name"]):
                continue
            package = await repo.create(
                AlgorithmPackage(
                    name=template["name"],
                    framework="ultralytics",
                    description=template["description"],
                )
            )
            root = StoragePaths.package_version_root(package.id, TEMPLATE_VERSION)
            root.mkdir(parents=True, exist_ok=True)

            runtime_config = {
                "labels": template["labels"],
                "domain": template["name"],
                "task": "detect",
                "train_defaults": template["train_defaults"],
                "metrics_entrypoint": "metrics.py:run",
                "metrics_config": template["metrics_config"],
            }
            files = {
                "inference.py": _inference_code(template),
                "metrics.py": _metrics_code(template),
                "manifest.json": json.dumps(_manifest(template), ensure_ascii=False, indent=2),
                "README.md": _readme(template),
            }
            for filename, content in files.items():
                (root / filename).write_text(content, encoding="utf-8")

            await version_repo.create(
                AlgorithmPackageVersion(
                    package_id=package.id,
                    version=TEMPLATE_VERSION,
                    entrypoint="inference.py:run",
                    runtime_config=runtime_config,
                    status="published",
                )
            )
        await session.commit()


if __name__ == "__main__":
    # Windows 下 psycopg 异步驱动需要 Selector 事件循环（与 run.py 保持一致）
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
