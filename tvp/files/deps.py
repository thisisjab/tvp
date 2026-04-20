from typing import Annotated

from fastapi import Depends

from tvp import config
from tvp.database.deps import DBSession
from tvp.files.minio.deps import MinioClient
from tvp.files.repo import FileRepo
from tvp.files.service import FileService
from tvp.redis.deps import RedisClient


def get_file_repo(db_session: DBSession) -> FileRepo:
    return FileRepo(db_session)


FileRepoDep = Annotated[FileRepo, Depends(get_file_repo)]


def get_file_service(
    file_repo: FileRepoDep, redis_client: RedisClient, minio: MinioClient
) -> FileService:
    return FileService(file_repo, redis_client, minio, bucket=config.minio.bucket_name)


FileServiceDep = Annotated[FileService, Depends(get_file_service)]
