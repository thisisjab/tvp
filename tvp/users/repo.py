from typing import Self

import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.users.models import User
from tvp.utils.repo import BaseDatabaseRepo


class UserRepo(BaseDatabaseRepo[User]):
    def __init__(self: Self, db_session: AsyncSession) -> None:
        super().__init__(db_session, User)

    async def get_user_by_username(self: Self, username: str) -> User | None:
        """Get user by username with lowercase."""
        query = sqla.select(User).where(
            sqla.func.lower(User.username) == username.lower()
        )
        return (await self._db_session.execute(query)).scalar_one_or_none()
