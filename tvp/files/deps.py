from typing import Annotated

from fastapi import Depends
from taskiq import TaskiqDepends

from tvp import config
from tvp.database.deps import DBSession, TaskiqDBSession
from tvp.files.minio.deps import MinioClient, TaskiqMinioClient
from tvp.files.repo import FileRepo
from tvp.files.service import FileService


def get_file_repo(db_session: DBSession) -> FileRepo:
    return FileRepo(db_session)


FileRepoDep = Annotated[FileRepo, Depends(get_file_repo)]


def get_file_service(file_repo: FileRepoDep, minio: MinioClient) -> FileService:
    return FileService(file_repo, minio, bucket=config.minio.bucket_name)


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


# Taskiq Dependencies
async def get_taskiq_file_repo(db_session: TaskiqDBSession) -> FileRepo:
    return FileRepo(db_session)


TaskiqFileRepoDep = Annotated[FileRepo, TaskiqDepends(get_taskiq_file_repo)]


async def get_taskiq_file_service(
    file_repo: TaskiqFileRepoDep,
    minio: TaskiqMinioClient,
) -> FileService:
    return FileService(file_repo, minio, bucket=config.minio.bucket_name)


TaskiqFileService = Annotated[FileService, TaskiqDepends(get_taskiq_file_service)]
