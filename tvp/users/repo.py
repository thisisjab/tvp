import uuid
from typing import Self
from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.users.models import User


class UserRepo:
    def __init__(self: Self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(self: Self, user: User) -> User:
        """Create user in database."""
        self._db_session.add(user)
        await self._db_session.commit()
        await self._db_session.refresh(user)
        return user

    async def get_by_id(self: Self, id_: UUID) -> User | None:
        """Get user by id (pk)."""
        query = sqla.select(User).where(User.id == id_)
        return (await self._db_session.execute(query)).scalar_one_or_none()

    async def get_by_username(self: Self, username: str) -> User | None:
        """Get user by username with lowercase."""
        query = sqla.select(User).where(
            sqla.func.lower(User.username) == username.lower()
        )
        return (await self._db_session.execute(query)).scalar_one_or_none()

    async def delete_by_id(self: Self, id_: UUID) -> None:
        """Delete a user by id."""
        query = sqla.delete(User).where(User.id == id_)
        await self._db_session.execute(query)
        await self._db_session.commit()


class InMemoryUserRepo:
    def __init__(self: Self) -> None:
        self._db: list[User] = []

    async def create(self: Self, user: User) -> User:
        user.id = uuid.uuid4()
        self._db.append(user)
        return user

    async def get_by_id(self: Self, id_: UUID) -> User | None:
        for u in self._db:
            if u.id == id_:
                return u

        return None

    async def get_by_username(self: Self, username: str) -> User | None:
        for u in self._db:
            if u.username == username:
                return u

        return None

    async def delete_by_id(self: Self, id_: UUID) -> None:
        for i, u in enumerate(self._db):
            if u.id == id_:
                self._db.pop(i)
                return

        msg = "User not found"
        raise ValueError(msg)
