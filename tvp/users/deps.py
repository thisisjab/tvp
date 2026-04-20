from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tvp.database.deps import DBSession
from tvp.redis.deps import RedisClient
from tvp.users.repo import UserRepo
from tvp.users.schemas import AuthenticateUserByAccessTokenRequest, UserSchema
from tvp.users.service import UserService


def get_user_repo(db_session: DBSession) -> UserRepo:
    return UserRepo(db_session)


UserRepoDep = Annotated[UserRepo, Depends(get_user_repo)]


def get_user_service(user_repo: UserRepoDep, redis_client: RedisClient) -> UserService:
    return UserService(user_repo, redis_client)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


_security = HTTPBearer()


async def get_current_user(
    user_service: UserServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> UserSchema:
    token = credentials.credentials

    return await user_service.authenticate_user_by_access_token(
        AuthenticateUserByAccessTokenRequest(token=token)
    )


CurrentUserDep = Annotated[UserSchema, Depends(get_current_user)]
