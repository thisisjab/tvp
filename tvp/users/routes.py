from fastapi import APIRouter

from tvp.users.constants import UserRole
from tvp.users.deps import UserServiceDep
from tvp.users.schemas import (
    AccessTokenSchema,
    CreateUserSchema,
    ObtainAccessTokenRequest,
    RegisterUserRequest,
    UserSchema,
)

users_router = APIRouter(tags=["Users"])


@users_router.post("/register")
async def register_user(
    req: RegisterUserRequest, user_service: UserServiceDep
) -> UserSchema:
    """Register a new user with `USER ` role."""
    return await user_service.create_user(
        CreateUserSchema(**req.model_dump(), role=UserRole.USER)
    )


@users_router.post("/obtain-access-token")
async def obtain_access_token(
    req: ObtainAccessTokenRequest, user_service: UserServiceDep
) -> AccessTokenSchema:
    """Obtain JWT access token which can be used for protected routes.

    Client must send `Authorization: Bearer <token>` in all request headers
    in order to be authenticated.
    """
    return await user_service.obtain_token(req)
