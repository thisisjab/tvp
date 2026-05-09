from fastapi import APIRouter

from tvp.users.routes import users_router
from tvp.videos.routes import videos_router

all_routes = APIRouter()

all_routes.include_router(users_router, prefix="/users")
all_routes.include_router(videos_router, prefix="/videos")
