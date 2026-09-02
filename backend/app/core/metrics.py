"""评测指标计算（纯函数，无 IO 依赖，可单测）。

提供 F-beta、按类别加权聚合等自定义指标，
供评测 worker 输出基础指标后在主进程侧计算。
"""

from __future__ import annotations

from typing import Any


def compute_fbeta(precision: float, recall: float, beta: float = 1.0) -> float:
    """F-beta = (1+beta^2) * P*R / (beta^2*P + R)；分母为 0 时返回 0。"""

    if beta <= 0:
        raise ValueError("beta 必须大于 0")
    denominator = beta * beta * precision + recall
    if denominator == 0:
        return 0.0
    return round((1 + beta * beta) * precision * recall / denominator, 4)


def aggregate_per_class_weighted(
    per_class: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
    beta: float = 1.0,
) -> dict[str, float]:
    """按类别加权聚合 precision/recall/F-beta/mAP50。

    weights: class_name -> 权重（默认等权）。仅统计出现在 per_class 中的类别。
    """

    if not per_class:
        return {
            "weighted_precision": 0.0,
            "weighted_recall": 0.0,
            "weighted_fbeta": 0.0,
            "weighted_map50": 0.0,
        }

    class_weights = weights or {}
    total_weight = 0.0
    acc_precision = 0.0
    acc_recall = 0.0
    acc_map50 = 0.0
    for row in per_class:
        class_name = str(row.get("class_name") or row.get("class_id"))
        weight = float(class_weights.get(class_name, 1.0))
        total_weight += weight
        acc_precision += float(row.get("precision") or 0.0) * weight
        acc_recall += float(row.get("recall") or 0.0) * weight
        acc_map50 += float(row.get("map50") or 0.0) * weight

    if total_weight <= 0:
        return {
            "weighted_precision": 0.0,
            "weighted_recall": 0.0,
            "weighted_fbeta": 0.0,
            "weighted_map50": 0.0,
        }

    weighted_precision = acc_precision / total_weight
    weighted_recall = acc_recall / total_weight
    return {
        "weighted_precision": round(weighted_precision, 4),
        "weighted_recall": round(weighted_recall, 4),
        "weighted_fbeta": compute_fbeta(weighted_precision, weighted_recall, beta),
        "weighted_map50": round(acc_map50 / total_weight, 4),
    }


def add_custom_metrics(
    metrics: dict[str, Any],
    *,
    per_class: list[dict[str, Any]],
    beta: float = 1.0,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """在评测指标结果上追加自定义指标（F-beta + 按类别加权聚合）。"""

    result = dict(metrics)
    result["fbeta"] = compute_fbeta(
        float(result.get("precision") or 0.0),
        float(result.get("recall") or 0.0),
        beta,
    )
    result["weighted"] = aggregate_per_class_weighted(per_class, weights, beta)

    per_class_rows = []
    for row in per_class:
        row_result = dict(row)
        row_result["fbeta"] = compute_fbeta(
            float(row.get("precision") or 0.0),
            float(row.get("recall") or 0.0),
            beta,
        )
        per_class_rows.append(row_result)
    result["per_class"] = per_class_rows
    result["custom_config"] = {"beta": beta, "weights": weights or {}}
    return result
