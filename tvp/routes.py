from fastapi import APIRouter

from tvp.files.routes import files_router
from tvp.users.routes import users_router

all_routes = APIRouter()

all_routes.include_router(files_router, prefix="/files")
all_routes.include_router(users_router, prefix="/users")
