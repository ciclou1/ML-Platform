# FastAPI dependencies use the established project router pattern.
# ruff: noqa: B008

import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db
from app.exceptions import NotFoundError
from app.schemas.task import TaskResponse
from app.schemas.video import VideoExtractRequest, VideoResponse
from app.services.video import VideoService

router = APIRouter(tags=["视频样本"])


def get_service(db: AsyncSession = Depends(get_db)) -> VideoService:
    return VideoService(db)


@router.get("/videos", response_model=list[VideoResponse], summary="查询数据集视频列表")
async def list_videos(
    dataset_id: uuid.UUID = Query(...),
    service: VideoService = Depends(get_service),
):
    return await service.list_by_dataset(dataset_id)


@router.post(
    "/datasets/{dataset_id}/videos",
    response_model=VideoResponse,
    status_code=201,
    summary="上传视频样本",
)
async def upload_video(
    dataset_id: uuid.UUID,
    file: UploadFile = File(...),
    service: VideoService = Depends(get_service),
):
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if file.size is not None and file.size > max_size:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        return await service.upload(
            dataset_id,
            file.filename or "video.mp4",
            file.file,
            max_size=max_size,
        )
    except NotFoundError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/videos/{video_id}/extract",
    response_model=TaskResponse,
    status_code=201,
    summary="创建视频抽帧任务",
)
async def extract_video_frames(
    video_id: uuid.UUID,
    data: VideoExtractRequest,
    service: VideoService = Depends(get_service),
):
    task = await service.create_extract_task(video_id, data)
    return task


@router.get("/videos/{video_id}/file", summary="获取视频文件")
async def get_video_file(video_id: uuid.UUID, service: VideoService = Depends(get_service)):
    path = await service.get_video_file_path(video_id)
    if not path:
        raise NotFoundError("Video file not found")
    return FileResponse(path=path, media_type=mimetypes.guess_type(path)[0] or "video/mp4")
