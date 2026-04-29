from typing import Self
from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.videos.models import Video


class VideoRepo:
    def __init__(self: Self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(self: Self, video: Video) -> Video:
        """Create video in database."""
        self._db_session.add(video)
        await self._db_session.commit()
        await self._db_session.refresh(video)
        return video

    async def update(self: Self, video: Video) -> Video:
        """Create video in database."""
        self._db_session.add(video)
        await self._db_session.commit()
        await self._db_session.refresh(video)
        return video

    async def exists_by_file_id(self: Self, file_id: UUID) -> bool:
        """Check if video exists for given `file_id`."""
        q = sqla.select(sqla.exists(Video)).where(Video.file_id == file_id)
        return (await self._db_session.execute(q)).scalar_one()
