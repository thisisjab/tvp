from collections.abc import Iterable
from typing import Self
from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.utils.pagination import PaginationParams
from tvp.videos.models import Video
from tvp.videos.schemas import VideoFilters, VideoFiltersContext


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

    async def exists_by_id(self: Self, id_: UUID) -> bool:
        """Check if video exists for given `id`."""
        q = sqla.select(sqla.exists(Video)).where(Video.id == id_)
        return (await self._db_session.execute(q)).scalar() or False

    async def get_by_id(self: Self, id_: UUID) -> Video | None:
        """Get video by its id."""
        q = sqla.select(Video).where(Video.id == id_)
        return (await self._db_session.execute(q)).scalar_one_or_none()

    async def get_all(
        self: Self,
        context: VideoFiltersContext,
        filters: VideoFilters,
        pagination_params: PaginationParams,
    ) -> tuple[int, Iterable[Video]]:
        """Get all videos with given criteria and return count of total items and return list of videos."""  # noqa: E501
        q = sqla.select(Video).where(
            (Video.is_public) | (Video.owner_id == context.user_id)
        )

        if filters.is_public is not None:
            q = q.where(Video.is_public == filters.is_public)

        if filters.owner_id is not None:
            q = q.where(Video.owner_id == filters.owner_id)

        if filters.title is not None:
            q = q.where(Video.title.like(filters.title))

        count_q = sqla.select(sqla.func.count()).select_from(q.subquery())

        q = (
            q.limit(pagination_params.page_size)
            .offset((pagination_params.page - 1) * pagination_params.page_size)
            .order_by(Video.created_at.desc())
        )

        total_count = (await self._db_session.execute(count_q)).scalar() or 0
        videos = (await self._db_session.execute(q)).scalars()

        return total_count, videos
