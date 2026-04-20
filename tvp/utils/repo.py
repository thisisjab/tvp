from typing import Self

import sqlalchemy as sqla
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.database.models import DatabaseModel


class BaseDatabaseRepo[T: DatabaseModel]:
    def __init__(self: Self, db_session: AsyncSession, model_class: type[T]) -> None:
        self._db_session = db_session
        self._model_class: type[T] = model_class

    async def create(self: Self, instance: T) -> T:
        """Create a new record in the database."""
        self._db_session.add(instance)
        await self._db_session.commit()
        await self._db_session.refresh(instance)
        return instance

    async def update(self: Self, instance: T) -> T:
        """Update an existing record in the database."""
        self._db_session.add(instance)
        await self._db_session.commit()
        await self._db_session.refresh(instance)
        return instance

    async def get(self: Self, *conditions: ColumnElement[bool]) -> T | None:
        """Get a single record by its attributes."""
        stmt = sqla.select(self._model_class).where(*conditions)
        result = await self._db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self: Self, *conditions: ColumnElement[bool]) -> None:
        """Delete a record by its attributes."""
        stmt = sqla.delete(self._model_class).where(*conditions)
        await self._db_session.execute(stmt)
