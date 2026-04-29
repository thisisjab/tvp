import sqlalchemy as sqla
from sqlalchemy.orm import Mapped, mapped_column

from tvp.database.models import DatabaseModel, TimestampedModelMixin, UUIDModelMixin
from tvp.users.constants import UserRole


class User(DatabaseModel, UUIDModelMixin, TimestampedModelMixin):
    """User represents a user in database."""

    username: Mapped[str] = mapped_column(
        sqla.types.String, nullable=False, unique=True
    )
    password: Mapped[str] = mapped_column(sqla.types.String, nullable=False)
    role: Mapped[UserRole] = mapped_column(sqla.types.Enum(UserRole), nullable=False)

    __tablename__ = "users"
