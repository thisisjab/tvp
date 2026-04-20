from fastapi import FastAPI

from tvp.errors.handlers import EXCEPTION_HANDLERS
from tvp.routes import all_routes

app = FastAPI(
    name="TVP",
    description="Tiny video party API",
    version="0.0.0",
    exception_handlers=EXCEPTION_HANDLERS,
)

app.include_router(all_routes)
