from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Mapped, mapped_column

from tvp.database.models import DatabaseModel, TimestampedModelMixin, UUIDModelMixin
from tvp.videos.constants import VideoVariantCode, VideoVariantProcessingState


class Video(DatabaseModel, UUIDModelMixin, TimestampedModelMixin):
    # TODO: create indexes

    file_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("uploaded_files.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    owner_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    duration_seconds: Mapped[float | None] = mapped_column(
        sqla.types.Float, nullable=True
    )

    master_playlist_file_id: Mapped[UUID | None] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("uploaded_files.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Public videos can be used by any user to be partied, otherwise videos are streamable only by the uploader  # noqa: E501
    is_public: Mapped[bool] = mapped_column(sqla.types.Boolean, nullable=False)

    title: Mapped[str] = mapped_column(sqla.types.String, nullable=False)
    description: Mapped[str | None] = mapped_column(
        sqla.types.String, nullable=True, default=None, server_default=None
    )

    __tablename__ = "videos"


class VideoVariant(DatabaseModel, TimestampedModelMixin):
    variant_code: Mapped[VideoVariantCode] = mapped_column(
        sqla.Enum(VideoVariantCode),
        nullable=False,
        primary_key=True,
    )

    video_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey(
            "videos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        primary_key=True,
    )

    file_id: Mapped[UUID | None] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey(
            "uploaded_files.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    playlist_file_id: Mapped[UUID | None] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey(
            "uploaded_files.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    state: Mapped[VideoVariantProcessingState] = mapped_column(
        sqla.types.Enum(VideoVariantProcessingState),
        nullable=False,
    )

    fps: float = mapped_column(sqla.Float, nullable=False)
    gop_size: int = mapped_column(sqla.Integer, nullable=False)
    video_bitrate: int = mapped_column(sqla.Integer, nullable=False)
    video_max_bitrate: int = mapped_column(sqla.Integer, nullable=False)
    video_buf_size: int = mapped_column(sqla.Integer, nullable=False)
    audio_bitrate: int = mapped_column(sqla.Integer, nullable=False)
    audio_sample_rate: int = mapped_column(sqla.Integer, nullable=False)

    __tablename__ = "video_variants"
