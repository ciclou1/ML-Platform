"""全局结构化日志配置。

在应用启动时调用 :func:`setup_logging`，将根日志输出统一为 JSON 行，
便于单机部署下用 ``docker logs`` / 日志采集工具直接解析。

- ``json_output=True`` 输出一行一个 JSON 对象；
- ``json_output=False`` 输出人类可读的 ``level name message`` 格式。
"""

from __future__ import annotations

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """将日志记录格式化为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    """配置根日志记录器。幂等：重复调用不会叠加 handler。"""

    root = logging.getLogger()
    # 清空既有 handler，避免重复输出（uvicorn 等库可能已挂载 handler）
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(
        JsonFormatter()
        if json_output
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(stream)
    root.setLevel(level.upper())
