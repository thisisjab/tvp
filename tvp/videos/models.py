from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Mapped, mapped_column

from tvp.database.models import DatabaseModel, TimestampedModelMixin, UUIDModelMixin


class Video(DatabaseModel, UUIDModelMixin, TimestampedModelMixin):
    # TODO: create indexes

    file_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("files.id", ondelete="PROTECT"),
        nullable=False,
        unique=True,
    )

    owner_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("users.id", ondelete="PROTECT"),
        nullable=False,
    )

    is_processed_for_streaming: Mapped[bool] = mapped_column(
        sqla.types.Boolean, nullable=False
    )

    total_seconds: Mapped[int | None] = mapped_column(sqla.types.Integer, nullable=True)

    # Public videos can be used by any user to be partied, otherwise videos are streamable only by the uploader  # noqa: E501
    is_public: Mapped[bool] = mapped_column(sqla.types.Boolean, nullable=False)

    title: Mapped[str] = mapped_column(sqla.types.String, nullable=False)
    description: Mapped[str | None] = mapped_column(
        sqla.types.String, nullable=True, default=None, server_default=None
    )

    __tablename__ = "videos"
