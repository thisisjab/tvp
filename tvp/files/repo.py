from typing import Self
from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.files.models import UploadedFile
from tvp.utils.datetime import get_now


class FileRepo:
    def __init__(self: Self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(self: Self, file: UploadedFile) -> UploadedFile:
        """Create an uploaded file record in the database."""
        self._db_session.add(file)
        await self._db_session.commit()
        await self._db_session.refresh(file)
        return file

    async def get_by_id(self: Self, id_: UUID) -> UploadedFile | None:
        """Fetch a file from database by its id."""
        q = sqla.select(UploadedFile).where(UploadedFile.id == id_)
        return (await self._db_session.execute(q)).scalar_one_or_none()

    async def exists_by_id(self: Self, id_: UUID) -> bool:
        """Check if file with given id exists in database."""
        q = sqla.select(sqla.exists(UploadedFile)).where(UploadedFile.id == id_)
        return (await self._db_session.execute(q)).scalar_one()


class InMemoryFileRepo:
    def __init__(self: Self) -> None:
        self._db: list[UploadedFile] = []

    async def create(self: Self, file: UploadedFile) -> UploadedFile:
        if self._db and any(f for f in self._db if f.id == file.id):
            msg = "File ID is duplicate"
            raise ValueError(msg)

        file.created_at = get_now()
        file.updated_at = get_now()
        self._db.append(file)
        return file

    async def get_by_id(self: Self, id_: UUID) -> UploadedFile | None:
        for f in self._db:
            if f.id == id_:
                return f

        return None

    async def exists_by_id(self: Self, id_: UUID) -> bool:
        return any(f for f in self._db if f.id == id_)
