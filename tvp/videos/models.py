from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Mapped, mapped_column

from tvp.database.models import DatabaseModel, TimestampedModelMixin
from tvp.videos.constants import VideoProcessingState


class Video(DatabaseModel, TimestampedModelMixin):
    # TODO: create indexes
    id: Mapped[UUID] = mapped_column(
        init=True,
        primary_key=True,
    )

    owner_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    state: VideoProcessingState = mapped_column(
        sqla.types.Enum(VideoProcessingState),
        nullable=False,
    )

    # Public videos can be used by any user to be partied, otherwise videos are streamable only by the uploader  # noqa: E501
    is_public: Mapped[bool] = mapped_column(sqla.types.Boolean, nullable=False)

    title: Mapped[str] = mapped_column(sqla.types.String, nullable=False)
    description: Mapped[str | None] = mapped_column(
        sqla.types.String, nullable=True, default=None, server_default=None
    )

    __tablename__ = "videos"
