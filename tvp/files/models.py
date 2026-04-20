from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Mapped, mapped_column

from tvp.database.models import DatabaseModel, TimestampedModelMixin, UUIDModelMixin


class UploadedFile(DatabaseModel, UUIDModelMixin, TimestampedModelMixin):
    """UploadedFile represents a successfuly uploaded file on the storage."""

    id: Mapped[UUID] = mapped_column(
        init=True,
        primary_key=True,
    )
    key: Mapped[str] = mapped_column(sqla.types.String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sqla.types.String, nullable=False)
    mimetype: Mapped[str] = mapped_column(sqla.types.String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(sqla.types.Integer, nullable=False)
    uploader_id: Mapped[UUID] = mapped_column(
        sqla.types.UUID,
        sqla.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    __tablename__: str = "uploaded_files"
    __table_args__: tuple[sqla.CheckConstraint] = (
        sqla.CheckConstraint(
            "size_bytes > 0",
            "size_gt_zero_check",
        ),
    )
