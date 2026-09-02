"""Loads an optional custom metric function from a trusted algorithm package."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def run_metric_entrypoint(
    entry_config: Mapping[str, Any], payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Run ``module.py:function(payload) -> dict`` declared by an algorithm package."""

    package_root = entry_config.get("package_root")
    entrypoint = entry_config.get("entrypoint")
    if not isinstance(package_root, str) or not isinstance(entrypoint, str):
        raise ValueError("Custom metric entrypoint configuration is incomplete")

    module_path, function_name = _resolve_entrypoint(Path(package_root), entrypoint)
    module = _load_module(module_path)
    metric_function = getattr(module, function_name)
    if not callable(metric_function):
        raise ValueError(f"Custom metric entrypoint is not callable: {entrypoint}")

    output = metric_function(dict(payload))
    if output is None:
        return {}
    if not isinstance(output, Mapping):
        raise ValueError("Custom metric entrypoint must return an object")
    return _json_object(output)


def _resolve_entrypoint(package_root: Path, entrypoint: str) -> tuple[Path, str]:
    module_name, separator, function_name = entrypoint.partition(":")
    module_relative = Path(module_name)
    if (
        not separator
        or not function_name
        or module_relative.is_absolute()
        or ".." in module_relative.parts
    ):
        raise ValueError(f"Invalid custom metric entrypoint: {entrypoint}")

    root = package_root.resolve()
    module_path = (root / module_relative).resolve()
    if not module_path.is_relative_to(root) or not module_path.is_file():
        raise ValueError(f"Custom metric module not found: {module_name}")
    return module_path, function_name


def _load_module(module_path: Path) -> object:
    spec = importlib.util.spec_from_file_location("algorithm_package_metrics", module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load custom metric module: {module_path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        normalized = json.loads(json.dumps(dict(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Custom metric output must be JSON serializable") from exc
    if not isinstance(normalized, dict):
        raise ValueError("Custom metric entrypoint must return an object")
    return normalized
