"""视频样本管理：上传、抽帧任务创建、抽帧结果落库。"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.storage.factory import get_storage
from app.core.storage.paths import StoragePaths
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.task import Task
from app.models.video import Video
from app.repositories.dataset import DatasetRepository, VideoRepository
from app.repositories.task import TaskRepository
from app.schemas.video import VideoExtractRequest

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


class VideoService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.video_repo = VideoRepository(session)
        self.dataset_repo = DatasetRepository(session)
        self.task_repo = TaskRepository(session)
        self.storage = get_storage()

    async def list_by_dataset(
        self, dataset_id: uuid.UUID, offset: int = 0, limit: int = 50
    ) -> list[Video]:
        return await self.video_repo.list_by_dataset(dataset_id, offset=offset, limit=limit)

    async def upload(
        self,
        dataset_id: uuid.UUID,
        filename: str,
        source,
        max_size: int | None = None,
    ) -> Video:
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise NotFoundError("Dataset not found")

        safe_filename = Path(filename or "").name.strip()
        suffix = Path(safe_filename).suffix.lower()
        if not safe_filename or suffix not in VIDEO_EXTS:
            raise ValidationError(
                f"Unsupported video format. Accepted formats: {', '.join(sorted(VIDEO_EXTS))}"
            )

        entity = Video(
            dataset_id=dataset_id,
            filename=safe_filename,
            file_path=str(StoragePaths.video_path(uuid.uuid4(), safe_filename)),
            status="uploaded",
        )
        entity = await self.video_repo.create(entity)

        relative = str(
            StoragePaths.video_path(entity.id, safe_filename).relative_to(settings.storage_path)
        )
        await self.storage.save_stream(relative, source, max_size=max_size)
        entity.file_path = str(StoragePaths.video_path(entity.id, safe_filename))
        return await self.video_repo.update(entity)

    async def create_extract_task(self, video_id: uuid.UUID, data: VideoExtractRequest) -> Task:
        video = await self.video_repo.get_by_id(video_id)
        if not video:
            raise NotFoundError("Video not found")
        if video.status == "processing":
            raise ConflictError("Video already has an extraction task in progress")

        if not (await self._video_path(video)).exists():
            raise ValidationError("Video file is missing from storage")

        config = {
            "video_id": str(video.id),
            "video_path": video.file_path,
            "dataset_id": str(video.dataset_id),
            "output_dir": str(
                StoragePaths.dataset_root(video.dataset_id) / "images" / str(video.id)
            ),
            "frame_interval_seconds": data.frame_interval_seconds,
            "split": data.split,
        }
        task = Task(
            name=f"{video.filename}-抽帧",
            task_type="video_import",
            dataset_id=video.dataset_id,
            config=config,
        )
        video.status = "processing"
        await self.video_repo.update(video)
        return await self.task_repo.create(task)

    async def get_video_file_path(self, video_id: uuid.UUID) -> str | None:
        video = await self.video_repo.get_by_id(video_id)
        if not video:
            return None
        path = await self._video_path(video)
        return str(path) if path.exists() and path.is_file() else None

    async def _video_path(self, video: Video) -> Path:
        from app.core.dataset_files import resolve_storage_path

        return resolve_storage_path(video.file_path)
