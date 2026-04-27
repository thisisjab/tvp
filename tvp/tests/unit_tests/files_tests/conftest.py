from unittest.mock import Mock

import pytest

from tvp.files.repo import InMemoryFileRepo
from tvp.files.service import FileRepoProtocol, FileService


@pytest.fixture
def file_repo() -> FileRepoProtocol:
    return InMemoryFileRepo()


@pytest.fixture
def file_service(file_repo: InMemoryFileRepo) -> FileService:
    minio = Mock()
    bucket = "test-bucket"
    return FileService(file_repo=file_repo, minio=minio, bucket=bucket)
