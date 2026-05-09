from datetime import datetime

from pydantic import BaseModel


class TemporaryUploadUrlSchema(BaseModel):
    url: str
    expires_at: datetime


class FileObjectInfo(BaseModel):
    key: str
    is_dir: bool
