from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tvp.errors.handlers import EXCEPTION_HANDLERS
from tvp.routes import all_routes
from tvp.taskiq import broker


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await broker.startup()
    yield
    await broker.shutdown()


app = FastAPI(
    name="TVP",
    description="Tiny video party API",
    version="0.0.0",
    exception_handlers=EXCEPTION_HANDLERS,
    lifespan=_lifespan,
)

app.include_router(all_routes)
