import json
import os
import sys
import traceback
from pathlib import Path

from app.core.storage.paths import StoragePaths
from app.core.workflow_engine import execute_workflow


def main() -> None:
    task_id = sys.argv[1]
    config = json.loads(StoragePaths.task_config(task_id).read_text(encoding="utf-8"))
    StoragePaths.task_pid(task_id).write_text(str(os.getpid()))
    result_file = StoragePaths.task_result(task_id)
    try:
        output = execute_workflow(
            config["graph"],
            Path(config["csv_path"]),
            StoragePaths.task_root(task_id) / "output.csv",
        )
        result_file.write_text(json.dumps({"status": "completed", **output}), encoding="utf-8")
    except Exception as exc:
        result_file.write_text(
            json.dumps(
                {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()}
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
