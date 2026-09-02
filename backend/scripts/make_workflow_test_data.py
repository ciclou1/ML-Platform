"""Generate sample CSV files for manual testing of the workflow editor.

Usage::

    uv run python scripts/make_workflow_test_data.py
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

OUTPUT_DIR = Path("test-data/workflow")

DEVICES = ("GEN-01", "GEN-02", "GEN-03")


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"created {path} ({len(rows)} rows)")


def make_clean_timeseries(path: Path) -> None:
    """三个设备 24 小时、每 6 分钟一条的干净时序，用于筛选/排序/分组等基础链路。"""
    rows: list[dict[str, str]] = []
    for step in range(240):
        hour = step * 6 // 60
        minute = step * 6 % 60
        timestamp = f"2026-09-01 {hour:02d}:{minute:02d}:00"
        for index, device in enumerate(DEVICES):
            base = 55 + index * 8
            temperature = base + 10 * math.sin((step + index * 20) / 12) + (step % 7) * 0.4
            current = 180 + 30 * math.cos((step + index * 30) / 15) + index * 12
            vibration = 2.0 + abs(math.sin((step + index * 10) / 9)) * 3.5
            rows.append(
                {
                    "timestamp": timestamp,
                    "device_id": device,
                    "temperature": f"{temperature:.2f}",
                    "current": f"{current:.1f}",
                    "vibration": f"{vibration:.2f}",
                }
            )
    _write(path, rows)


def make_dirty_data(path: Path) -> None:
    """含缺失值 / 重复行 / 异常值的脏数据，用于去重、筛选、质检类算子。"""
    rows: list[dict[str, str]] = []
    statuses = ("running", "idle", "alarm")
    for step in range(48):
        timestamp = f"2026-09-02 {step // 2:02d}:{(step % 2) * 30:02d}:00"
        device = DEVICES[step % 3]
        status = statuses[step % 3]
        temperature = f"{40 + step * 0.8:.2f}"
        rows.append(
            {
                "timestamp": timestamp,
                "device_id": device,
                "status": status,
                "temperature": temperature,
            }
        )

    # 制造脏数据特征
    rows[5]["temperature"] = ""          # 缺失值
    rows[11]["status"] = ""              # 缺失值
    rows[20]["temperature"] = "999.00"   # 异常高值
    rows[30]["temperature"] = "-5.00"    # 异常低值
    rows.append(dict(rows[2]))           # 完全重复行
    rows.append(dict(rows[17]))          # 完全重复行
    rows.append(dict(rows[40]))          # 完全重复行
    _write(path, rows)


def make_device_catalog(path: Path) -> None:
    """设备台账小表，用于分组/关联类演示。"""
    rows = [
        {"device_id": "GEN-01", "device_name": "1号发电机", "line": "A线"},
        {"device_id": "GEN-02", "device_name": "2号发电机", "line": "A线"},
        {"device_id": "GEN-03", "device_name": "3号发电机", "line": "B线"},
        {"device_id": "TR-01", "device_name": "1号主变", "line": "B线"},
    ]
    _write(path, rows)


def main() -> None:
    base = Path(__file__).resolve().parents[2] / OUTPUT_DIR
    make_clean_timeseries(base / "generator_timeseries.csv")
    make_dirty_data(base / "sensor_dirty.csv")
    make_device_catalog(base / "device_catalog.csv")


if __name__ == "__main__":
    main()
