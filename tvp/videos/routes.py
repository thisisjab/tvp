from fastapi import APIRouter

from tvp.users.deps import CurrentUserDep
from tvp.videos.deps import VideoServiceDep
from tvp.videos.schemas import CreateVideoRequest, CreateVideoSchema, VideoSchema

videos_router = APIRouter(tags=["Video"])


@videos_router.post("")
async def create_video(
    req: CreateVideoRequest, video_service: VideoServiceDep, user: CurrentUserDep
) -> VideoSchema:
    """Create a video inside user's collection."""
    return await video_service.create_video(
        CreateVideoSchema(**req.model_dump(), owner_id=user.id)
    )
