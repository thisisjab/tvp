from typing import Annotated

import minio
from fastapi import Depends

from tvp.files.minio.connection import get_minio

MinioClient = Annotated[minio.Minio, Depends(get_minio)]
