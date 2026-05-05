from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import Context, TaskiqDepends

from tvp.database.connection import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_taskiq_db(
    context: Annotated[Context, TaskiqDepends()],
) -> AsyncGenerator[AsyncSession]:
    async with context.state.session_maker() as session:
        yield session


TaskiqDBSession = Annotated[AsyncSession, TaskiqDepends(get_taskiq_db)]
