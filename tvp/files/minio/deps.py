from typing import Annotated

import minio
from fastapi import Depends
from taskiq import Context, TaskiqDepends

from tvp.files.minio.connection import get_minio

MinioClient = Annotated[minio.Minio, Depends(get_minio)]


async def get_taskiq_minio(
    context: Annotated[Context, TaskiqDepends()],
) -> minio.Minio:
    return context.state.minio


TaskiqMinioClient = Annotated[minio.Minio, TaskiqDepends(get_taskiq_minio)]
