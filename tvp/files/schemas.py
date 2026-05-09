from datetime import datetime

from pydantic import BaseModel


class TemporaryUploadUrlSchema(BaseModel):
    url: str
    expires_at: datetime


class FileObjectInfo(BaseModel):
    name: str
    key: str
    is_dir: bool
