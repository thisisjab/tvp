from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tvp.database.connection import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]
