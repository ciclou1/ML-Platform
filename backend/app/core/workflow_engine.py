"""CSV workflow execution primitives used by the isolated workflow worker.

全部算子共享一组通用配置字段（前端检查器按算子渲染）：

- ``column``:     主输入列
- ``value``:      值参数（数值 / 文本；多值用逗号分隔，如 clamp 的 "min,max"）
- ``target``:     输出列名（缺省时按算子默认规则；变换类默认就地覆盖或加后缀）
- ``count``:      数量参数（窗口大小 / 保留条数 / 分桶数 / 小数位）
- ``descending``: 排序方向
- ``columns``:    列名列表（select_columns / drop_columns）
- ``second_csv``: 关联表 CSV 路径（join / union）
"""

from __future__ import annotations

import csv
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

OPERATOR_CATALOG = [
    "csv_source",
    "select_columns",
    "rename_columns",
    "drop_columns",
    "fill_missing",
    "filter_equals",
    "filter_contains",
    "filter_gt",
    "filter_lt",
    "sort",
    "limit",
    "deduplicate",
    "add_constant",
    "cast_number",
    "add",
    "subtract",
    "multiply",
    "divide",
    "absolute",
    "round",
    "clamp",
    "moving_average",
    "cumulative_sum",
    "difference",
    "normalize_minmax",
    "zscore",
    "bucket",
    "threshold",
    "flag_range",
    "group_count",
    "group_sum",
    "group_mean",
    "group_min",
    "group_max",
    "aggregate_count",
    "aggregate_sum",
    "aggregate_mean",
    "aggregate_min",
    "aggregate_max",
    "rolling_min",
    "rolling_max",
    "rolling_std",
    "top_n",
    "bottom_n",
    "sample",
    "pivot_count",
    "join",
    "union",
    "quality_missing",
    "quality_duplicates",
    "export_csv",
]

_ROW_OPS = "row"
_TABLE_OPS = "table"


def execute_workflow(graph: dict[str, Any], csv_path: Path, output_path: Path) -> dict[str, Any]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    rows = _read_csv(csv_path)
    for node in _ordered_nodes(nodes, graph.get("edges")):
        if not isinstance(node, dict):
            continue
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        rows = _apply_node(rows, str(data.get("operator") or node.get("type") or ""), data)
    _write_csv(rows, output_path)
    return {
        "rows": len(rows),
        "columns": list(rows[0]) if rows else [],
        "output_path": str(output_path),
    }


def _ordered_nodes(nodes: list[Any], edges: Any) -> list[dict[str, Any]]:
    normalized_nodes = [node for node in nodes if isinstance(node, dict)]
    by_id = {
        str(node.get("id") or f"node-{index}"): node
        for index, node in enumerate(normalized_nodes)
    }
    indegree = {node_id: 0 for node_id in by_id}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for edge in edges if isinstance(edges, list) else []:
        if not isinstance(edge, dict):
            continue
        source, target = str(edge.get("source")), str(edge.get("target"))
        if source in by_id and target in by_id:
            outgoing[source].append(target)
            indegree[target] += 1
    ready = [node_id for node_id, value in indegree.items() if value == 0]
    ordered: list[dict[str, Any]] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(by_id[node_id])
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if len(ordered) != len(by_id):
        raise ValueError("Workflow graph contains a cycle")
    return ordered


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def _apply_node(
    rows: list[dict[str, str]], node_type: str, data: dict[str, Any]
) -> list[dict[str, str]]:
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    column = str(config.get("column") or "")
    value = config.get("value")
    target = str(config.get("target") or "")
    count = _to_int(config.get("count"), 0)

    handler = _HANDLERS.get(node_type)
    if handler is None:
        return rows
    return handler(rows, config, column, value, target, count)


def _read_second_csv(config: dict[str, Any]) -> list[dict[str, str]]:
    """读取 join / union 使用的关联表 CSV。"""

    path_value = str(config.get("second_csv") or "").strip()
    if not path_value:
        raise ValueError("该算子需要在检查器中选择关联表 CSV")
    path = Path(path_value)
    if not path.is_file():
        raise ValueError(f"关联表 CSV 不存在: {path_value}")
    return _read_csv(path)


# ---------------------------------------------------------------------------
# 行级算子
# ---------------------------------------------------------------------------


def _op_csv_source(rows, config, column, value, target, count):
    return rows


def _op_export_csv(rows, config, column, value, target, count):
    return rows


def _op_select_columns(rows, config, column, value, target, count):
    columns = _columns_param(config, value)
    if not columns:
        return rows
    return [{key: row.get(key, "") for key in columns} for row in rows]


def _op_drop_columns(rows, config, column, value, target, count):
    columns = set(_columns_param(config, value)) | ({column} if column else set())
    if not columns:
        return rows
    return [
        {key: item for key, item in row.items() if key not in columns}
        for row in rows
    ]


def _op_rename_columns(rows, config, column, value, target, count):
    mapping = _mapping_param(value)
    if column and target:
        mapping[column] = target
    if not mapping:
        return rows
    return [
        {mapping.get(key, key): item for key, item in row.items()}
        for row in rows
    ]


def _op_fill_missing(rows, config, column, value, target, count):
    fill = "" if value is None else str(value)
    keys = [column] if column else None
    return [_fill_row(row, fill, keys) for row in rows]


def _op_filter_equals(rows, config, column, value, target, count):
    expected = "" if value is None else str(value)
    return [row for row in rows if row.get(column, "") == expected]


def _op_filter_contains(rows, config, column, value, target, count):
    needle = "" if value is None else str(value)
    return [row for row in rows if needle in row.get(column, "")]


def _op_filter_gt(rows, config, column, value, target, count):
    return _filter_number(rows, column, _to_float(value, 0.0), lambda a, b: a > b)


def _op_filter_lt(rows, config, column, value, target, count):
    return _filter_number(rows, column, _to_float(value, 0.0), lambda a, b: a < b)


def _op_sort(rows, config, column, value, target, count):
    descending = bool(config.get("descending"))
    if column and _all_numeric(rows, column):
        return sorted(rows, key=lambda row: _to_float(row.get(column, ""), 0.0), reverse=descending)
    return sorted(rows, key=lambda row: row.get(column, ""), reverse=descending)


def _op_limit(rows, config, column, value, target, count):
    return rows[: max(count, 0)]


def _op_deduplicate(rows, config, column, value, target, count):
    seen: set[str] = set()
    result = []
    for row in rows:
        key = row.get(column, "") if column else "\x00".join(row.values())
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _op_add_constant(rows, config, column, value, target, count):
    output = target or column or "constant"
    return [{**row, output: "" if value is None else str(value)} for row in rows]


def _op_cast_number(rows, config, column, value, target, count):
    if not column:
        return rows
    return [{**row, column: _format_number(_to_float(row.get(column, ""), 0.0))} for row in rows]


def _op_add(rows, config, column, value, target, count):
    return _arithmetic(rows, column, _to_float(value, 0.0), target, lambda a, b: a + b, "add")


def _op_subtract(rows, config, column, value, target, count):
    return _arithmetic(rows, column, _to_float(value, 0.0), target, lambda a, b: a - b, "sub")


def _op_multiply(rows, config, column, value, target, count):
    return _arithmetic(rows, column, _to_float(value, 0.0), target, lambda a, b: a * b, "mul")


def _op_divide(rows, config, column, value, target, count):
    return _arithmetic(
        rows, column, _to_float(value, 0.0), target, lambda a, b: a / b if b else 0.0, "div"
    )


def _op_absolute(rows, config, column, value, target, count):
    if not column:
        return rows
    return [
        {**row, column: _format_number(abs(_to_float(row.get(column, ""), 0.0)))}
        for row in rows
    ]


def _op_round(rows, config, column, value, target, count):
    if not column:
        return rows
    digits = count if count else int(_to_float(value, 2.0))
    return [
        {**row, column: _format_number(round(_to_float(row.get(column, ""), 0.0), digits))}
        for row in rows
    ]


def _op_clamp(rows, config, column, value, target, count):
    if not column:
        return rows
    low, high = _pair_param(value)
    return [
        {
            **row,
            column: _format_number(
                min(high, max(low, _to_float(row.get(column, ""), 0.0)))
            ),
        }
        for row in rows
    ]


def _op_moving_average(rows, config, column, value, target, count):
    window = count or int(_to_float(value, 3.0))
    return _rolling(rows, column, window, target, "ma", statistics.fmean)


def _op_cumulative_sum(rows, config, column, value, target, count):
    if not column:
        return rows
    output = target or f"{column}_cumsum"
    total = 0.0
    result = []
    for row in rows:
        total += _to_float(row.get(column, ""), 0.0)
        result.append({**row, output: _format_number(total)})
    return result


def _op_difference(rows, config, column, value, target, count):
    if not column:
        return rows
    output = target or f"{column}_diff"
    previous: float | None = None
    result = []
    for row in rows:
        current = _to_float(row.get(column, ""), 0.0)
        delta = "" if previous is None else _format_number(current - previous)
        result.append({**row, output: delta})
        previous = current
    return result


def _op_normalize_minmax(rows, config, column, value, target, count):
    if not column or not rows:
        return rows
    numbers = [_to_float(row.get(column, ""), 0.0) for row in rows]
    low, high = min(numbers), max(numbers)
    span = high - low
    output = target or f"{column}_norm"
    return [
        {
            **row,
            output: _format_number((number - low) / span if span else 0.0),
        }
        for row, number in zip(rows, numbers, strict=False)
    ]


def _op_zscore(rows, config, column, value, target, count):
    if not column or not rows:
        return rows
    numbers = [_to_float(row.get(column, ""), 0.0) for row in rows]
    mean = statistics.fmean(numbers)
    std = statistics.pstdev(numbers)
    output = target or f"{column}_z"
    return [
        {**row, output: _format_number((number - mean) / std if std else 0.0)}
        for row, number in zip(rows, numbers, strict=False)
    ]


def _op_bucket(rows, config, column, value, target, count):
    if not column or not rows:
        return rows
    buckets = count or int(_to_float(value, 5.0))
    numbers = [_to_float(row.get(column, ""), 0.0) for row in rows]
    low, high = min(numbers), max(numbers)
    span = high - low
    output = target or f"{column}_bucket"
    result = []
    for row, number in zip(rows, numbers, strict=False):
        index = min(int((number - low) / span * buckets), buckets - 1) if span else 0
        result.append({**row, output: str(index + 1)})
    return result


def _op_threshold(rows, config, column, value, target, count):
    if not column:
        return rows
    threshold_value = _to_float(value, 0.0)
    output = target or f"{column}_flag"
    return [
        {**row, output: "1" if _to_float(row.get(column, ""), 0.0) >= threshold_value else "0"}
        for row in rows
    ]


def _op_flag_range(rows, config, column, value, target, count):
    if not column:
        return rows
    low, high = _pair_param(value)
    output = target or f"{column}_in_range"
    return [
        {
            **row,
            output: "yes" if low <= _to_float(row.get(column, ""), 0.0) <= high else "no",
        }
        for row in rows
    ]


def _op_quality_missing(rows, config, column, value, target, count):
    output = target or "missing_flag"
    keys = [column] if column else None
    return [
        {
            **row,
            output: "yes" if _has_missing(row, keys) else "no",
        }
        for row in rows
    ]


def _op_quality_duplicates(rows, config, column, value, target, count):
    output = target or "duplicate_flag"
    seen: set[str] = set()
    result = []
    for row in rows:
        key = row.get(column, "") if column else "\x00".join(row.values())
        result.append({**row, output: "yes" if key in seen else "no"})
        seen.add(key)
    return result


# ---------------------------------------------------------------------------
# 分组 / 聚合算子
# ---------------------------------------------------------------------------


def _op_group_count(rows, config, column, value, target, count):
    counter = Counter(row.get(column, "") for row in rows)
    return [{column: key, "count": str(number)} for key, number in counter.items()]


def _op_group_sum(rows, config, column, value, target, count):
    return _group_aggregate(rows, column, str(value or ""), target, sum, "sum")


def _op_group_mean(rows, config, column, value, target, count):
    return _group_aggregate(rows, column, str(value or ""), target, statistics.fmean, "mean")


def _op_group_min(rows, config, column, value, target, count):
    return _group_aggregate(rows, column, str(value or ""), target, min, "min")


def _op_group_max(rows, config, column, value, target, count):
    return _group_aggregate(rows, column, str(value or ""), target, max, "max")


def _op_aggregate_count(rows, config, column, value, target, count):
    output = target or "count"
    return [{output: str(len(rows))}]


def _op_aggregate_sum(rows, config, column, value, target, count):
    return _whole_aggregate(rows, column, target, sum, "sum")


def _op_aggregate_mean(rows, config, column, value, target, count):
    return _whole_aggregate(rows, column, target, statistics.fmean, "mean")


def _op_aggregate_min(rows, config, column, value, target, count):
    return _whole_aggregate(rows, column, target, min, "min")


def _op_aggregate_max(rows, config, column, value, target, count):
    return _whole_aggregate(rows, column, target, max, "max")


def _op_rolling_min(rows, config, column, value, target, count):
    return _rolling(rows, column, count or int(_to_float(value, 3.0)), target, "rmin", min)


def _op_rolling_max(rows, config, column, value, target, count):
    window = count or int(_to_float(value, 3.0))
    return _rolling(rows, column, window, target, "rmax", max)


def _op_rolling_std(rows, config, column, value, target, count):
    window = count or int(_to_float(value, 3.0))
    return _rolling(rows, column, window, target, "rstd", _pstdev_or_zero)


def _op_top_n(rows, config, column, value, target, count):
    return _top_n(rows, column, count or int(_to_float(value, 10.0)), largest=True)


def _op_bottom_n(rows, config, column, value, target, count):
    return _top_n(rows, column, count or int(_to_float(value, 10.0)), largest=False)


def _op_sample(rows, config, column, value, target, count):
    """确定性均匀采样：等间隔抽取 count 行（count<=0 时不过滤）。"""

    total = len(rows)
    if count <= 0 or count >= total or total == 0:
        return rows
    step = total / count
    return [rows[min(int(index * step), total - 1)] for index in range(count)]


def _op_pivot_count(rows, config, column, value, target, count):
    """按 column（行键）与 value（列键）交叉计数，输出透视表。"""

    row_keys: list[str] = []
    col_keys: list[str] = []
    counter: Counter[tuple[str, str]] = Counter()
    for row in rows:
        row_key = row.get(column, "")
        col_key = row.get(str(value or ""), "")
        if row_key not in row_keys:
            row_keys.append(row_key)
        if col_key not in col_keys:
            col_keys.append(col_key)
        counter[(row_key, col_key)] += 1
    return [
        {column: row_key, **{col_key: str(counter[(row_key, col_key)]) for col_key in col_keys}}
        for row_key in row_keys
    ]


def _op_join(rows, config, column, value, target, count):
    """左连接：按 column（左键）= target（右键，缺省同名）从关联表引入列。"""

    second_rows = _read_second_csv(config)
    if not column or not second_rows:
        return rows
    right_key = target or column
    introduce = _columns_param(config, value)
    if not introduce:
        introduce = [key for key in second_rows[0] if key != right_key]

    index: dict[str, dict[str, str]] = {}
    for row in second_rows:
        index.setdefault(row.get(right_key, ""), row)

    result = []
    for row in rows:
        matched = index.get(row.get(column, ""))
        merged = dict(row)
        for key in introduce:
            merged[f"{key}_joined" if key == column else key] = (
                matched.get(key, "") if matched else ""
            )
        result.append(merged)
    return result


def _op_union(rows, config, column, value, target, count):
    """纵向合并主表与关联表，取列的并集（缺失补空）。"""

    second_rows = _read_second_csv(config)
    columns: list[str] = []
    for row in [*rows, *second_rows]:
        for key in row:
            if key not in columns:
                columns.append(key)
    return [
        {key: row.get(key, "") for key in columns}
        for row in [*rows, *second_rows]
    ]


_HANDLERS = {
    "csv_source": _op_csv_source,
    "select_columns": _op_select_columns,
    "rename_columns": _op_rename_columns,
    "drop_columns": _op_drop_columns,
    "fill_missing": _op_fill_missing,
    "filter_equals": _op_filter_equals,
    "filter_contains": _op_filter_contains,
    "filter_gt": _op_filter_gt,
    "filter_lt": _op_filter_lt,
    "sort": _op_sort,
    "limit": _op_limit,
    "deduplicate": _op_deduplicate,
    "add_constant": _op_add_constant,
    "cast_number": _op_cast_number,
    "add": _op_add,
    "subtract": _op_subtract,
    "multiply": _op_multiply,
    "divide": _op_divide,
    "absolute": _op_absolute,
    "round": _op_round,
    "clamp": _op_clamp,
    "moving_average": _op_moving_average,
    "cumulative_sum": _op_cumulative_sum,
    "difference": _op_difference,
    "normalize_minmax": _op_normalize_minmax,
    "zscore": _op_zscore,
    "bucket": _op_bucket,
    "threshold": _op_threshold,
    "flag_range": _op_flag_range,
    "group_count": _op_group_count,
    "group_sum": _op_group_sum,
    "group_mean": _op_group_mean,
    "group_min": _op_group_min,
    "group_max": _op_group_max,
    "aggregate_count": _op_aggregate_count,
    "aggregate_sum": _op_aggregate_sum,
    "aggregate_mean": _op_aggregate_mean,
    "aggregate_min": _op_aggregate_min,
    "aggregate_max": _op_aggregate_max,
    "rolling_min": _op_rolling_min,
    "rolling_max": _op_rolling_max,
    "rolling_std": _op_rolling_std,
    "top_n": _op_top_n,
    "bottom_n": _op_bottom_n,
    "sample": _op_sample,
    "pivot_count": _op_pivot_count,
    "join": _op_join,
    "union": _op_union,
    "quality_missing": _op_quality_missing,
    "quality_duplicates": _op_quality_duplicates,
    "export_csv": _op_export_csv,
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_number(number: float) -> str:
    if math.isnan(number) or math.isinf(number):
        return ""
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _columns_param(config: dict[str, Any], value: Any) -> list[str]:
    columns = config.get("columns")
    if isinstance(columns, list) and columns:
        return [str(item).strip() for item in columns if str(item).strip()]
    if isinstance(columns, str) and columns.strip():
        return [item.strip() for item in columns.split(",") if item.strip()]
    if value:
        return [item.strip() for item in str(value).split(",") if item.strip()]
    return []


def _mapping_param(value: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in str(value or "").split(","):
        old, _, new = pair.partition("=")
        if old.strip() and new.strip():
            mapping[old.strip()] = new.strip()
    return mapping


def _pair_param(value: Any) -> tuple[float, float]:
    parts = str(value or "").split(",")
    low = _to_float(parts[0] if parts else None, 0.0)
    high = _to_float(parts[1] if len(parts) > 1 else None, low)
    return min(low, high), max(low, high)


def _filter_number(rows, column: str, threshold: float, predicate):
    return [
        row
        for row in rows
        if predicate(_to_float(row.get(column, ""), float("nan")), threshold)
    ]


def _arithmetic(rows, column: str, operand: float, target: str, op, suffix: str):
    if not column:
        return rows
    output = target or column
    return [
        {**row, output: _format_number(op(_to_float(row.get(column, ""), 0.0), operand))}
        for row in rows
    ]


def _rolling(rows, column: str, window: int, target: str, suffix: str, reducer):
    if not column:
        return rows
    window = max(window, 1)
    output = target or f"{column}_{suffix}"
    numbers = [_to_float(row.get(column, ""), 0.0) for row in rows]
    result = []
    for index in range(len(rows)):
        window_values = numbers[max(0, index - window + 1) : index + 1]
        result.append({**rows[index], output: _format_number(reducer(window_values))})
    return result


def _pstdev_or_zero(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _group_aggregate(rows, key_column: str, value_column: str, target: str, reducer, suffix: str):
    if not key_column or not value_column:
        raise ValueError("分组聚合需要同时配置分组列（column）与数值列（value）")
    groups: dict[str, list[float]] = {}
    order: list[str] = []
    for row in rows:
        key = row.get(key_column, "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(_to_float(row.get(value_column, ""), 0.0))
    output = target or f"{value_column}_{suffix}"
    return [
        {key_column: key, output: _format_number(reducer(groups[key]))}
        for key in order
    ]


def _whole_aggregate(rows, column: str, target: str, reducer, suffix: str):
    if not column:
        raise ValueError("聚合算子需要配置数值列（column）")
    numbers = [_to_float(row.get(column, ""), 0.0) for row in rows]
    output = target or f"{column}_{suffix}"
    value = len(rows) if suffix == "count" else reducer(numbers) if numbers else 0.0
    return [{output: _format_number(float(value))}]


def _top_n(rows, column: str, count: int, *, largest: bool):
    if not column:
        return rows
    ordered = sorted(
        rows,
        key=lambda row: _to_float(row.get(column, ""), 0.0),
        reverse=largest,
    )
    return ordered[: max(count, 0)]


def _fill_row(row: dict[str, str], fill: str, keys: list[str] | None) -> dict[str, str]:
    result = dict(row)
    for key in keys if keys is not None else row.keys():
        if not str(row.get(key, "")).strip():
            result[key] = fill
    return result


def _row_keys(row: dict[str, str], keys: list[str] | None) -> list[str]:
    return keys if keys is not None else list(row.keys())


def _has_missing(row: dict[str, str], keys: list[str] | None) -> bool:
    return not all(str(row.get(key, "")).strip() for key in _row_keys(row, keys))


def _all_numeric(rows, column: str) -> bool:
    return bool(rows) and all(_is_number(row.get(column, "")) for row in rows)


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return str(value).strip() != ""
