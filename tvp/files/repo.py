from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from tvp.files.models import UploadedFile
from tvp.utils.repo import BaseDatabaseRepo


class FileRepo(BaseDatabaseRepo[UploadedFile]):
    def __init__(self: Self, db_session: AsyncSession) -> None:
        super().__init__(db_session, UploadedFile)
