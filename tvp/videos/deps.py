from typing import Annotated

from fastapi import Depends

from tvp.database.deps import DBSession
from tvp.files.deps import FileServiceDep
from tvp.redis.deps import RedisClient
from tvp.videos.repo import VideoRepo
from tvp.videos.service import VideoService


def get_video_repo(db_session: DBSession) -> VideoRepo:
    return VideoRepo(db_session)


VideoRepoDep = Annotated[VideoRepo, Depends(get_video_repo)]


def get_video_service(
    video_repo: VideoRepoDep, file_service: FileServiceDep, redis_client: RedisClient
) -> VideoService:
    return VideoService(video_repo, file_service, redis_client)


VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]
