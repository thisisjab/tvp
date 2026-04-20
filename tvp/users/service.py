from datetime import timedelta
from typing import Self

from pydantic import BaseModel
from redis.asyncio import Redis

from tvp import config
from tvp.errors import FieldsError, UnathenticatedUserError
from tvp.users.models import User
from tvp.users.repo import UserRepo
from tvp.users.schemas import (
    AccessTokenSchema,
    AuthenticateUserByAccessTokenRequest,
    CreateUserSchema,
    ObtainAccessTokenRequest,
    UserSchema,
)
from tvp.users.utils import create_jwt, password_hasher, validate_jwt
from tvp.utils.datetime import get_now
from tvp.utils.redis import RedisLock


class _AccessTokenJWTSchema(BaseModel):
    user_id: str


class UserService:
    def __init__(self: Self, user_repo: UserRepo, redis: Redis) -> None:
        self._user_repo = user_repo
        self._redis = redis

        self.jwt_expiry = timedelta(seconds=config.jwt.auth_token_expiry_seconds)

    async def create_user(self: Self, req: CreateUserSchema) -> UserSchema:
        """This method is called whenever a user of ANY role needs to be created."""  # noqa: D401, D404
        # Lock current username in redis so that concurrent clients asking
        # to obtain a common username do not run into race condition.
        async with RedisLock(
            redis=self._redis,
            # NOTE: Since lock name is only used here, I didn't create
            # this key in cache_keys file of users module.
            lock_name=f"user-registration#{req.username}",
        ):
            if await self._user_repo.get_user_by_username(req.username) is not None:
                raise FieldsError({"username": ["This username is already taken."]})

            # Hash password
            password_hash = password_hasher.hash(plain_text=req.plain_password)

            # Save user to database
            user = await self._user_repo.create(
                User(
                    username=req.username,
                    password=password_hash,
                    role=req.role,
                )
            )

            return UserSchema.model_validate(user, from_attributes=True)

    async def obtain_token(
        self: Self, req: ObtainAccessTokenRequest
    ) -> AccessTokenSchema:
        """Obtain token by validating combination of username and password."""
        # TODO: prevent password timing attacks

        # Validate username and password
        user = await self._user_repo.get_user_by_username(req.username)
        if user is None:
            raise UnathenticatedUserError

        if not password_hasher.verify(
            hash_=user.password, plain_text=req.plain_password
        ):
            raise UnathenticatedUserError

        # Create token
        expires_at = get_now() + self.jwt_expiry
        token = create_jwt(
            _AccessTokenJWTSchema(user_id=str(user.id)), expires_at=expires_at
        )

        return AccessTokenSchema(user_id=user.id, token=token, expires_at=expires_at)

    async def authenticate_user_by_access_token(
        self: Self, req: AuthenticateUserByAccessTokenRequest
    ) -> UserSchema:
        """Check if token hasn't reached its expiry and is not black-listed.

        Additional steps like checking if user is still active, and not removed are
        taken as well.
        """
        # TODO: check if token is black-listed
        # TODO: check if user is active

        payload = validate_jwt(req.token, _AccessTokenJWTSchema)
        if payload is None:  # Token is expired or has incorrect signature/data
            raise UnathenticatedUserError

        user = await self._user_repo.get(User.id == payload.user_id)
        if user is None:
            raise UnathenticatedUserError

        return UserSchema.model_validate(user, from_attributes=True)
