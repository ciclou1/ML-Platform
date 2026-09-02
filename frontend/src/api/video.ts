import request from './request'
import { appendAccessToken } from './accessToken'
import type { Video } from '@/types/dataset'

export function getVideos(datasetId: string) {
  return request.get<never, Video[]>('/videos', { params: { dataset_id: datasetId } })
}

export function videoFileUrl(videoId: string) {
  return appendAccessToken(`/api/v1/videos/${videoId}/file`)
}

export function uploadVideo(datasetId: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post<never, Video>(`/datasets/${datasetId}/videos`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function extractVideoFrames(
  videoId: string,
  data: { frame_interval_seconds: number; split?: string },
) {
  return request.post<never, { id: string; task_type: string; status: string }>(
    `/videos/${videoId}/extract`,
    data,
  )
}
