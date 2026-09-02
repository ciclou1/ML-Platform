from __future__ import annotations

import json
import sys
import uuid

from PIL import Image

from app.config import settings
from app.core.storage.paths import StoragePaths
from app.runners import preprocess_worker


def test_preprocess_worker_writes_resize_outputs_and_zip(tmp_path, monkeypatch) -> None:
    storage_root = tmp_path / "storage"
    source = tmp_path / "source.png"
    Image.new("RGB", (80, 40), color=(30, 90, 160)).save(source)
    task_id = str(uuid.uuid4())
    task_root = storage_root / "tasks" / task_id
    task_root.mkdir(parents=True)
    (task_root / "config.json").write_text(
        json.dumps(
            {
                "preprocess_type": "resize",
                "width": 32,
                "height": 24,
                "output_format": "jpg",
                "source_images": [{"filename": "source.png", "file_path": str(source)}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "storage_root", str(storage_root))
    monkeypatch.setattr(sys, "argv", ["preprocess_worker", task_id])
    preprocess_worker.main()

    result = json.loads(StoragePaths.task_result(task_id).read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["processed_images"] == 1
    assert StoragePaths.task_output_file(task_id, "manifest.json").exists()
    assert StoragePaths.task_output_file(task_id, "output.zip").exists()
    output = next(StoragePaths.task_output_root(task_id).glob("images/*.jpg"))
    with Image.open(output) as image:
        assert image.size == (32, 24)
