from typing import Annotated

from fastapi import Depends
from taskiq import TaskiqDepends

from tvp.database.deps import DBSession, TaskiqDBSession
from tvp.files.deps import FileServiceDep, TaskiqFileServiceDep
from tvp.redis.deps import RedisClient, TaskiqRedisClient
from tvp.videos.repo import VideoRepo
from tvp.videos.service import VideoService


def get_video_repo(db_session: DBSession) -> VideoRepo:
    return VideoRepo(db_session)


VideoRepoDep = Annotated[VideoRepo, Depends(get_video_repo)]


def get_video_service(
    video_repo: VideoRepoDep,
    file_service: FileServiceDep,
    redis_client: RedisClient,
) -> VideoService:
    return VideoService(video_repo, file_service, redis_client)


VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]


# Taskiq Dependencies
def get_taskiq_video_repo(db_session: TaskiqDBSession) -> VideoRepo:
    return VideoRepo(db_session)


TaskiqVideoRepoDep = Annotated[VideoRepo, TaskiqDepends(get_taskiq_video_repo)]


def get_taskiq_video_service(
    video_repo: TaskiqVideoRepoDep,
    file_service: TaskiqFileServiceDep,
    redis_client: TaskiqRedisClient,
) -> VideoService:
    return VideoService(video_repo, file_service, redis_client)


TaskiqVideoServiceDep = Annotated[VideoService, TaskiqDepends(get_taskiq_video_service)]
