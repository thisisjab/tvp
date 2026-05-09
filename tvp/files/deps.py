from typing import Annotated

from fastapi import Depends
from taskiq import TaskiqDepends

from tvp import config
from tvp.files.minio.deps import MinioClient, TaskiqMinioClient
from tvp.files.service import FileService


def get_file_service(minio: MinioClient) -> FileService:
    return FileService(minio, bucket=config.minio.bucket_name)


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


# Taskiq Dependencies
async def get_taskiq_file_service(
    minio: TaskiqMinioClient,
) -> FileService:
    return FileService(minio, bucket=config.minio.bucket_name)


TaskiqFileServiceDep = Annotated[FileService, TaskiqDepends(get_taskiq_file_service)]
