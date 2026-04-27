from typing import Self
from unittest.mock import patch

import pytest

from tvp.errors import FieldsError, UnathenticatedUserError
from tvp.users.constants import UserRole
from tvp.users.schemas import (
    AuthenticateUserByAccessTokenSchema,
    CreateUserSchema,
    ObtainAccessTokenSchema,
)
from tvp.users.service import UserService, _AccessTokenJWTSchema
from tvp.users.utils import password_hasher, validate_jwt


class TestUserService:
    @pytest.mark.parametrize(
        "req",
        [
            CreateUserSchema(
                username="david", plain_password="this-is-secret", role=UserRole.ADMIN
            ),
            CreateUserSchema(
                username="jackson",
                plain_password="this-is-secret",
                role=UserRole.CONTENT_EDITOR,
            ),
            CreateUserSchema(
                username="jackson", plain_password="this-is-secret", role=UserRole.USER
            ),
        ],
    )
    async def test_create_user_with_valid_data(
        self: Self, req: CreateUserSchema, user_service: UserService
    ) -> None:
        """Test if valid data creates user."""
        # Arrange
        with patch("tvp.users.service.RedisLock") as mock_redis_lock:
            mock_redis_lock.aquire.return_value = True

            # Act
            user = await user_service.create_user(req)

            # Assert
            assert user.username == req.username
            assert user.role == req.role

    @pytest.mark.parametrize(
        "req",
        [
            CreateUserSchema(
                username="david", plain_password="this-is-secret", role=UserRole.ADMIN
            ),
            CreateUserSchema(
                username="jackson",
                plain_password="this-is-secret",
                role=UserRole.CONTENT_EDITOR,
            ),
            CreateUserSchema(
                username="jackson", plain_password="this-is-secret", role=UserRole.USER
            ),
        ],
    )
    async def test_create_user_hashes_password_correctly(
        self: Self, req: CreateUserSchema, user_service: UserService
    ):
        # Arrange
        with patch("tvp.users.service.RedisLock") as mock_redis_lock:
            mock_redis_lock.aquire.return_value = True

            # Act
            user = await user_service.create_user(req)
            user = await user_service._user_repo.get_by_id(user.id)  # noqa: SLF001

            assert user is not None
            assert user.password != req.plain_password  # Ensure hashed
            assert (
                password_hasher.verify(
                    hash_=user.password, plain_text=req.plain_password
                )
                is True
            )

    async def test_create_user_handles_duplicate_usernames(
        self: Self, user_service: UserService
    ) -> None:
        """Test if creating a user with already taken username, raises proper FieldsError."""  # noqa: E501
        # Arrange
        req = CreateUserSchema(
            username="jose-white",
            plain_password="something_random_but_secret",
            role=UserRole.USER,
        )

        with patch("tvp.users.service.RedisLock") as mock_redis_lock:
            mock_redis_lock.aquire.return_value = True

            # Act
            await user_service.create_user(req)
            with pytest.raises(FieldsError) as e:
                await user_service.create_user(req)

            # Assert
            assert e.value == FieldsError(
                {"username": ["This username is already taken."]}
            )

    @pytest.mark.parametrize(
        "req",
        [ObtainAccessTokenSchema(username="jackson", password="something-secret")],
    )
    async def test_obtain_access_token_with_valid_data(
        self: Self, req: ObtainAccessTokenSchema, user_service: UserService
    ) -> None:
        """Test valid access token is issued for valid combination of username/password."""  # noqa: E501
        # Arrange
        user = await user_service.create_user(
            CreateUserSchema(
                username=req.username,
                plain_password=req.plain_password,
                role=UserRole.ADMIN,
            )
        )

        # Act
        token = await user_service.obtain_access_token(req)
        token_body = validate_jwt(token.token, _AccessTokenJWTSchema)

        # Assert
        assert token_body is not None
        assert token_body.user_id == str(user.id)

    @pytest.mark.parametrize(
        "req",
        [ObtainAccessTokenSchema(username="jackson", password="something-secret")],
    )
    async def test_obtain_access_token_with_invalid_username(
        self: Self, req: ObtainAccessTokenSchema, user_service: UserService
    ) -> None:
        """Test access token is not created for non-existing username."""
        # Arrange
        await user_service.create_user(
            CreateUserSchema(
                username=req.username,
                plain_password=req.plain_password,
                role=UserRole.ADMIN,
            )
        )

        # Act
        req.username = "something-that-does-not-exist"
        with pytest.raises(UnathenticatedUserError) as e:
            await user_service.obtain_access_token(req)

        # Assert
        assert e.value == UnathenticatedUserError()

    @pytest.mark.parametrize(
        "req",
        [ObtainAccessTokenSchema(username="jackson", password="something-secret")],
    )
    async def test_obtain_access_token_with_invalid_password(
        self: Self, req: ObtainAccessTokenSchema, user_service: UserService
    ) -> None:
        """Test access token is not created for non-existing username."""
        # Arrange
        await user_service.create_user(
            CreateUserSchema(
                username=req.username,
                plain_password=req.plain_password,
                role=UserRole.ADMIN,
            )
        )

        # Act
        req.plain_password = "this is different than original secret"  # noqa: S105
        with pytest.raises(UnathenticatedUserError) as e:
            await user_service.obtain_access_token(req)

        # Assert
        assert e.value == UnathenticatedUserError()

    @pytest.mark.parametrize(
        "create_user_schema",
        [
            CreateUserSchema(
                username="jesse-pinkman",
                plain_password="jesse-is-not-fring",
                role=UserRole.ADMIN,
            )
        ],
    )
    async def test_authenticate_user_with_valid_access_token(
        self: Self, create_user_schema: CreateUserSchema, user_service: UserService
    ) -> None:
        """Test if valid token returns correct user."""
        # Arrange
        user = await user_service.create_user(create_user_schema)
        token = await user_service.obtain_access_token(
            ObtainAccessTokenSchema(
                username=create_user_schema.username,
                password=create_user_schema.plain_password,
            )
        )

        # Act
        authenticated_user = await user_service.authenticate_user_by_access_token(
            AuthenticateUserByAccessTokenSchema(token=token.token)
        )

        # Assert
        assert user == authenticated_user

    @pytest.mark.parametrize(
        "create_user_schema",
        [
            CreateUserSchema(
                username="jesse-pinkman",
                plain_password="jesse-is-not-fring",
                role=UserRole.ADMIN,
            )
        ],
    )
    async def test_authenticate_user_with_invalid_access_token(
        self: Self, create_user_schema: CreateUserSchema, user_service: UserService
    ) -> None:
        """Test if invalid token raises UnathenticatedUserError."""
        # Arrange
        await user_service.create_user(create_user_schema)

        # Act
        with pytest.raises(UnathenticatedUserError) as e:
            await user_service.authenticate_user_by_access_token(
                AuthenticateUserByAccessTokenSchema(token="invalid token")
            )

        # Assert
        assert e.value == UnathenticatedUserError()

    @pytest.mark.parametrize(
        "create_user_schema",
        [
            CreateUserSchema(
                username="jesse-pinkman",
                plain_password="jesse-is-not-fring",
                role=UserRole.ADMIN,
            )
        ],
    )
    async def test_authenticate_user_with_non_existing_user(
        self: Self, create_user_schema: CreateUserSchema, user_service: UserService
    ) -> None:
        """Test if valid token for a removed user raises UnathenticatedUserError."""
        # Arrange
        user = await user_service.create_user(create_user_schema)
        token = await user_service.obtain_access_token(
            ObtainAccessTokenSchema(
                username=create_user_schema.username,
                password=create_user_schema.plain_password,
            )
        )
        await user_service._user_repo.delete_by_id(user.id)  # noqa: SLF001

        # Act
        with pytest.raises(UnathenticatedUserError) as e:
            await user_service.authenticate_user_by_access_token(
                AuthenticateUserByAccessTokenSchema(token=token.token)
            )

        # Assert
        assert e.value == UnathenticatedUserError()
