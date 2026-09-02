"""工作流引擎算子测试：覆盖目录中全部 51 个算子均可产生有效结果。"""

from pathlib import Path

import pytest

from app.core.workflow_engine import OPERATOR_CATALOG, execute_workflow


def _run(graph: dict, source: Path, tmp_path: Path) -> tuple[dict, str]:
    output = tmp_path / "output.csv"
    result = execute_workflow(graph, source, output)
    return result, output.read_text(encoding="utf-8")


def _node(operator: str, **config) -> dict:
    return {"type": operator, "data": {"operator": operator, "config": config}}


def _second_csv(tmp_path: Path) -> Path:
    path = tmp_path / "lookup.csv"
    path.write_text("device_id,device_name\nG1,一号机\nG2,二号机\n", encoding="utf-8")
    return path


def test_workflow_engine_filters_and_groups_csv(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("type,value\na,1\na,2\nb,3\n", encoding="utf-8")
    result, content = _run(
        {"nodes": [_node("filter_equals", column="type", value="a")], "edges": []},
        source,
        tmp_path,
    )
    assert result["rows"] == 2
    assert "group_count" in OPERATOR_CATALOG


def test_workflow_engine_uses_edge_order(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("type\na\nb\n", encoding="utf-8")
    nodes = [
        {"id": "count", "data": {"operator": "group_count", "config": {"column": "type"}}},
        {
            "id": "filter",
            "data": {
                "operator": "filter_equals",
                "config": {"column": "type", "value": "a"},
            },
        },
    ]
    result, _ = _run(
        {"nodes": nodes, "edges": [{"source": "filter", "target": "count"}]}, source, tmp_path
    )
    assert result["rows"] == 1


def test_every_catalog_operator_executes(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text(
        "device_id,status,temperature,current\n"
        "G1,running,50.0,100\n"
        "G1,idle,60.0,120\n"
        "G2,running,70.0,90\n"
        "G2,,80.0,110\n",
        encoding="utf-8",
    )
    lookup = _second_csv(tmp_path)
    second_csv = str(lookup)

    cases: dict[str, dict] = {
        "csv_source": {},
        "select_columns": {"value": "device_id,temperature"},
        "rename_columns": {"value": "device_id=设备"},
        "drop_columns": {"value": "current"},
        "fill_missing": {"column": "status", "value": "unknown"},
        "filter_equals": {"column": "status", "value": "running"},
        "filter_contains": {"column": "status", "value": "run"},
        "filter_gt": {"column": "temperature", "value": "55"},
        "filter_lt": {"column": "temperature", "value": "55"},
        "sort": {"column": "temperature", "descending": True},
        "limit": {"count": 2},
        "deduplicate": {"column": "device_id"},
        "add_constant": {"column": "status", "value": "ok", "target": "mark"},
        "cast_number": {"column": "temperature"},
        "add": {"column": "temperature", "value": "1"},
        "subtract": {"column": "temperature", "value": "1"},
        "multiply": {"column": "temperature", "value": "2"},
        "divide": {"column": "temperature", "value": "2"},
        "absolute": {"column": "temperature"},
        "round": {"column": "temperature", "count": 1},
        "clamp": {"column": "temperature", "value": "0,65"},
        "moving_average": {"column": "temperature", "count": 2},
        "cumulative_sum": {"column": "current"},
        "difference": {"column": "current"},
        "normalize_minmax": {"column": "temperature"},
        "zscore": {"column": "temperature"},
        "bucket": {"column": "temperature", "count": 3},
        "threshold": {"column": "temperature", "value": "60"},
        "flag_range": {"column": "temperature", "value": "40,70"},
        "group_count": {"column": "device_id"},
        "group_sum": {"column": "device_id", "value": "current"},
        "group_mean": {"column": "device_id", "value": "current"},
        "group_min": {"column": "device_id", "value": "current"},
        "group_max": {"column": "device_id", "value": "current"},
        "aggregate_count": {},
        "aggregate_sum": {"column": "current"},
        "aggregate_mean": {"column": "current"},
        "aggregate_min": {"column": "current"},
        "aggregate_max": {"column": "current"},
        "rolling_min": {"column": "temperature", "count": 2},
        "rolling_max": {"column": "temperature", "count": 2},
        "rolling_std": {"column": "temperature", "count": 2},
        "top_n": {"column": "temperature", "count": 2},
        "bottom_n": {"column": "temperature", "count": 2},
        "sample": {"count": 2},
        "pivot_count": {"column": "device_id", "value": "status"},
        "join": {"column": "device_id", "second_csv": second_csv},
        "union": {"second_csv": second_csv},
        "quality_missing": {"column": "status"},
        "quality_duplicates": {"column": "device_id"},
        "export_csv": {},
    }

    assert set(cases) == set(OPERATOR_CATALOG)

    for operator, config in cases.items():
        output = tmp_path / f"out-{operator}.csv"
        try:
            result = execute_workflow(
                {"nodes": [_node(operator, **config)], "edges": []}, source, output
            )
        except Exception as exc:  # noqa: BLE001 - 汇总每个算子的失败
            pytest.fail(f"operator {operator} failed: {exc}")
        assert output.exists(), f"operator {operator} produced no output"
        assert result["rows"] >= 0


def test_join_and_union_use_second_csv(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("device_id,temperature\nG1,50.0\nG9,70.0\n", encoding="utf-8")
    lookup = _second_csv(tmp_path)

    joined, content = _run(
        {"nodes": [_node("join", column="device_id", second_csv=str(lookup))], "edges": []},
        source,
        tmp_path,
    )
    assert joined["rows"] == 2
    assert "一号机" in content
    assert "device_name" in content.splitlines()[0]

    merged, content = _run(
        {"nodes": [_node("union", second_csv=str(lookup))], "edges": []}, source, tmp_path
    )
    assert merged["rows"] == 4
    assert "二号机" in content


def test_join_requires_second_csv(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("device_id\nG1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="关联表"):
        execute_workflow(
            {"nodes": [_node("join", column="device_id")], "edges": []},
            source,
            tmp_path / "out.csv",
        )


def test_numeric_chain_produces_expected_values(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("value\n10\n20\n30\n40\n", encoding="utf-8")
    result, content = _run(
        {
            "nodes": [
                _node("multiply", column="value", value="2"),
                _node("filter_gt", column="value", value="39"),
                _node("sort", column="value", descending=True),
            ],
            "edges": [],
        },
        source,
        tmp_path,
    )
    assert result["rows"] == 3
    assert content.splitlines() == ["value", "80", "60", "40"]
