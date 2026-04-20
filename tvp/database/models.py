from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import MetaData, text, types
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from sqlalchemy.sql import func

naming_convention = {
    "ix": "ix_%(column_0_label)s",  # index name
    "uq": "uq_%(table_name)s_%(column_0_name)s",  # unique constraint
    "ck": "ck_%(table_name)s_%(constraint_name)s",  # check constraint
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",  # foreign key
    "pk": "pk_%(table_name)s",  # primary key
}


metadata = MetaData(naming_convention=naming_convention)


class DatabaseModel(MappedAsDataclass, DeclarativeBase):
    """Base class for any database model."""

    metadata = metadata
    type_annotation_map: ClassVar = {
        datetime: types.DateTime(timezone=True),
        list[str]: types.ARRAY(types.String),
    }


class UUIDModelMixin(MappedAsDataclass):
    id: Mapped[UUID] = mapped_column(
        init=False,
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    )


class AutoIncrementIDModelMixin(MappedAsDataclass):
    id: Mapped[int] = mapped_column(
        init=False,
        autoincrement=True,
        primary_key=True,
    )


class TimestampedModelMixin(MappedAsDataclass):
    # Since we are using postgres, there is no need to worry about timezone.
    # By default it's saved as UTC; so, later on we can convert it.

    created_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )
