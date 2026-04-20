from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from tvp.users.constants import UserRole


class UserSchema(BaseModel):
    """UserSchema defines a user object stored in database."""

    id: UUID
    username: str
    role: UserRole


class CreateUserSchema(BaseModel):
    """CreateUserSchema is what UserService accepts for creating new user."""

    username: str = Field(min_length=5)
    plain_password: str = Field(min_length=8)
    role: UserRole


class RegisterUserRequest(BaseModel):
    """RegisterUserRequest is the request schema for users to register.

    By default registered users are regular users (UserRole.USER). This
    is why the role field is omitted.
    """

    username: str = Field(min_length=5)
    plain_password: str = Field(min_length=8, alias="password")


class ObtainAccessTokenRequest(BaseModel):
    """
    ObtainAccessTokenRequest is the request schema for users/clients to
    get a JWT token which can be used for athentication in protected routes.
    """  # noqa: D205

    username: str
    plain_password: str = Field(alias="password")


class AccessTokenSchema(BaseModel):
    """AccessTokenSchema defines the successful response for obtaining access token."""

    token: str
    expires_at: datetime
    user_id: UUID


class AuthenticateUserByAccessTokenRequest(BaseModel):
    """
    AuthenticateUserByAccessTokenRequest is used by user service to retrieve ACTIVE
    user from the given access token with access token is still valid.

    Refer to user service for more info.
    """  # noqa: D205

    token: str
