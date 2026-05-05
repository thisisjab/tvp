from typing import Self
from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.videos.constants import VideoVariantCode
from tvp.videos.models import Video, VideoVariant


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
        return (await self._db_session.execute(q)).scalar() or False

    async def get_by_id(self: Self, id_: UUID) -> Video | None:
        """Get video by its id."""
        q = sqla.select(Video).where(Video.id == id_)
        return (await self._db_session.execute(q)).scalar_one_or_none()


class VideoVariantRepo:
    def __init__(self: Self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(self: Self, variant: VideoVariant) -> VideoVariant:
        """Create video variant in database."""
        self._db_session.add(variant)
        await self._db_session.commit()
        await self._db_session.refresh(variant)
        return variant

    async def update(self: Self, variant: VideoVariant) -> VideoVariant:
        """Create video variant in database."""
        self._db_session.add(variant)
        await self._db_session.commit()
        await self._db_session.refresh(variant)
        return variant

    async def get_by_video_id_and_code(
        self: Self, video_id: UUID, variant_code: VideoVariantCode
    ) -> VideoVariant | None:
        """Get video variant by its code and video id."""
        q = sqla.select(VideoVariant).where(
            VideoVariant.variant_code == variant_code
            and VideoVariant.video_id == video_id
        )
        return (await self._db_session.execute(q)).scalar_one_or_none()
