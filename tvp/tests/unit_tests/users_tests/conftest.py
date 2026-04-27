from unittest.mock import AsyncMock

import pytest

from tvp.users.repo import InMemoryUserRepo
from tvp.users.service import UserService


@pytest.fixture
def user_repo() -> InMemoryUserRepo:
    return InMemoryUserRepo()


@pytest.fixture
def user_service(user_repo: InMemoryUserRepo) -> UserService:
    redis = AsyncMock()
    return UserService(user_repo=user_repo, redis=redis)
