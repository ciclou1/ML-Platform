"""Algorithm package inference worker — runs in a separate process.

Usage: python -m app.runners.package_worker <task_id>

Reads config from storage/tasks/{task_id}/config.json
Writes result to storage/tasks/{task_id}/result.json

加载算法包内 entrypoint（如 inference.py:run），以子进程隔离 + 超时限制执行。
入口函数签名: run(payload: dict) -> dict
payload 包含 {"params": {...}} 及可选的输入文件路径。
"""

import importlib.util
import json
import sys
import time

from pathlib import Path


def _load_entrypoint(module_path: Path) -> object:
    spec = importlib.util.spec_from_file_location("pkg_inference", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载入口模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python -m app.runners.package_worker <task_id>")

    task_id = sys.argv[1]

    from app.core.storage.paths import StoragePaths

    config_file = StoragePaths.task_config(task_id)
    if not config_file.exists():
        sys.exit(f"Config file not found: {config_file}")

    config = json.loads(config_file.read_text())
    result_file = StoragePaths.task_result(task_id)

    package_root = config.get("package_root")
    entrypoint = config.get("entrypoint")
    if not package_root or not entrypoint:
        result_file.write_text(json.dumps({"status": "failed", "error": "缺少 package_root/entrypoint"}))
        sys.exit(1)

    root = Path(package_root)
    module_name, _, func_name = entrypoint.partition(":")
    module_path = root / module_name
    if not module_path.exists():
        result_file.write_text(json.dumps({"status": "failed", "error": f"入口文件不存在: {module_path}"}))
        sys.exit(1)

    started_at = time.time()
    try:
        module = _load_entrypoint(module_path)
        func = getattr(module, func_name or "run")
        payload = {"params": config.get("params") or {}}
        output = func(payload)
        if output is None:
            output = {}
        result_file.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "output": output,
                    "duration_ms": round((time.time() - started_at) * 1000, 2),
                }
            )
        )
    except Exception as exc:
        result_file.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(exc),
                    "duration_ms": round((time.time() - started_at) * 1000, 2),
                }
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
