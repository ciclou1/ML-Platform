"""Video frame extraction worker — runs in a separate process.

Usage: python -m app.runners.video_import_worker <task_id>

Reads config from storage/tasks/{task_id}/config.json
Writes progress to storage/tasks/{task_id}/progress.json
Writes result (帧清单 manifest) to storage/tasks/{task_id}/result.json

主进程在 sync_result 时依据 manifest 落库 Image / Video 记录。
"""

import json
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _progress_file(task_id: str):
    from app.core.storage.paths import StoragePaths

    return StoragePaths.task_progress(task_id)


def _write_progress(task_id: str, done: int, total: int) -> None:
    pct = int((done / total) * 100) if total > 0 else 0
    _progress_file(task_id).write_text(
        json.dumps({"progress": pct, "frames_done": done, "frames_total": total})
    )


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: python -m app.runners.video_import_worker <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]

    import cv2

    from app.core.storage.paths import StoragePaths

    config_file = StoragePaths.task_config(task_id)
    if not config_file.exists():
        logger.error("Config file not found: %s", config_file)
        sys.exit(1)

    config = json.loads(config_file.read_text())
    StoragePaths.task_pid(task_id).write_text(str(time.time_ns() // 1000))

    video_path = config.get("video_path")
    output_dir = config.get("output_dir")
    interval = max(1, int(config.get("frame_interval_seconds") or 1))
    result_file = StoragePaths.task_result(task_id)

    if not video_path or not output_dir:
        result_file.write_text(
            json.dumps({"status": "failed", "error": "缺少 video_path/output_dir 配置"})
        )
        sys.exit(1)

    from pathlib import Path

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_s = (total_frames / fps) if fps > 0 else 0.0

        frames: list[dict] = []
        frame_index = 0
        extracted = 0
        last_report = time.time()

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % interval == 0:
                filename = f"frame_{frame_index:06d}.jpg"
                frame_path = output_root / filename
                ok_write, buf = cv2.imencode(".jpg", frame)
                if ok_write:
                    frame_path.write_bytes(buf.tobytes())
                    height, width = frame.shape[:2]
                    frames.append(
                        {
                            "filename": filename,
                            "width": int(width),
                            "height": int(height),
                            "file_path": str(frame_path),
                            "frame_index": frame_index,
                        }
                    )
                    extracted += 1
            frame_index += 1
            if time.time() - last_report > 1.0:
                _write_progress(task_id, frame_index, total_frames or 1)
                last_report = time.time()

        cap.release()
        _write_progress(task_id, frame_index, total_frames or frame_index)

        result_file.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "fps": round(fps, 2),
                    "duration_s": round(duration_s, 2),
                    "frame_count": len(frames),
                    "frames": frames,
                }
            )
        )
        logger.info("Video import completed: %d frames", len(frames))
    except Exception as exc:
        result_file.write_text(
            json.dumps({"status": "failed", "error": str(exc)})
        )
        logger.exception("Video import failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
