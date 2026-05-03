import uuid
from typing import Self
from unittest.mock import Mock, patch
from uuid import UUID

import minio
import pytest

import tvp.files.storage_keys
from tvp.errors import BadRequestError, FieldsError
from tvp.files.models import UploadedFile
from tvp.files.schemas import (
    ConfirmFileUploadSchema,
    CreateUploadRequestSchema,
)
from tvp.files.service import FileService, _FileUploadRequestJWTSchema
from tvp.users.utils import validate_jwt


class TestFileService:
    @pytest.mark.parametrize(
        "req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="first-file",
                mimetype="a",
                size_bytes=1024,  # Highest possible value
            ),
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="second-file",
                mimetype="b",
                size_bytes=1,  # Lowest possible value
            ),
        ],
    )
    async def test_create_upload_request_with_valid_data(
        self: Self, req: CreateUploadRequestSchema, file_service: FileService
    ) -> None:
        """Test upload request with valid mimetype & accepted size_bytes is created."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a", "b"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        file_service._minio.presigned_put_object.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        # Act
        upload_request = await file_service.create_upload_request(req)
        upload_request_jwt_body = validate_jwt(
            upload_request.request_token, _FileUploadRequestJWTSchema
        )

        # Assert
        assert upload_request.upload_url == "some-url"
        assert upload_request_jwt_body is not None

    @pytest.mark.parametrize(
        "req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="first-file",
                mimetype="xyz",
                size_bytes=1,
            ),
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="second-file",
                mimetype="qrs",
                size_bytes=2,
            ),
        ],
    )
    async def test_create_upload_request_with_invalid_mimetype(
        self: Self, req: CreateUploadRequestSchema, file_service: FileService
    ) -> None:
        """Test if upload request with invalid mimetype raise proper error."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a", "b"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Act
        with pytest.raises(FieldsError) as e:
            await file_service.create_upload_request(req)

        # Assert
        assert e.value == FieldsError({"mimetype": ["This mimetype is not allowed."]})

    @pytest.mark.parametrize(
        "req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="first-file",
                mimetype="a",
                size_bytes=0,
            ),
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="second-file",
                mimetype="b",
                size_bytes=1025,
            ),
        ],
    )
    async def test_create_upload_request_with_invalid_size(
        self: Self, req: CreateUploadRequestSchema, file_service: FileService
    ) -> None:
        """Test if upload request with invalid file size bytes raise proper error."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a", "b"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Act
        with pytest.raises(FieldsError) as e:
            await file_service.create_upload_request(req)

        # Assert
        assert e.value == FieldsError(
            {
                "size_bytes": [
                    f"Upload size_bytes must be between 1 and {file_service.MAX_FILE_SIZE_BYTES}."  # noqa: E501
                ]
            }
        )

    @pytest.mark.parametrize(
        "create_upload_req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="file",
                mimetype="a",
                size_bytes=10,
            ),
        ],
    )
    async def test_confirm_upload_with_valid_data(
        self: Self,
        create_upload_req: CreateUploadRequestSchema,
        file_service: FileService,
    ) -> None:
        """Test valid token stores file in database if file is uploaded to bucket."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a", "b"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Mocks
        mock_object_stat = Mock()
        mock_object_stat.size = create_upload_req.size_bytes
        file_service._minio.stat_object.return_value = mock_object_stat  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        mock_object_binary = Mock()
        mock_object_binary.read.return_value = b"fake image binary data"
        file_service._minio.get_object.return_value = mock_object_binary  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        file_service._minio.get_presigned_url.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        file_service._minio.presigned_put_object.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        # Reading generated token's content
        upload_request = await file_service.create_upload_request(create_upload_req)
        token_body = validate_jwt(
            upload_request.request_token, _FileUploadRequestJWTSchema
        )

        # Act
        with patch(
            "tvp.files.service.magic.from_buffer",
            return_value=create_upload_req.mimetype,
        ):
            result = await file_service.confirm_upload(
                ConfirmFileUploadSchema(
                    request_token=upload_request.request_token,
                    uploader_id=create_upload_req.uploader_id,
                )
            )

        # Assert
        assert token_body is not None
        assert str(result.id) == token_body.generated_file_id
        assert result.key == tvp.files.storage_keys.file_upload_key(
            result.mimetype, result.id
        )
        assert result.size_bytes == create_upload_req.size_bytes
        assert result.mimetype == create_upload_req.mimetype
        assert result.url == "some-url"
        assert result.uploader_id == create_upload_req.uploader_id

    @pytest.mark.parametrize(
        "create_upload_req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="file",
                mimetype="a",
                size_bytes=10,
            ),
        ],
    )
    async def test_confirm_upload_with_invalid_token(
        self: Self,
        create_upload_req: CreateUploadRequestSchema,
        file_service: FileService,
    ) -> None:
        """Test invalid token raises bad request."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a", "b"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Mocks
        mock_object_stat = Mock()
        mock_object_stat.size = create_upload_req.size_bytes
        file_service._minio.stat_object.side_effect = minio.error.S3Error(  # ty:ignore[unresolved-attribute]  # noqa: SLF001
            code="NoSuchKey",
            message="The specified key does not exist",
            resource="/bucket/key",
            request_id="123",
            host_id="456",
            response=Mock(),
        )

        file_service._minio.presigned_put_object.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        upload_request = await file_service.create_upload_request(create_upload_req)

        # Act
        with pytest.raises(BadRequestError) as e:
            await file_service.confirm_upload(
                ConfirmFileUploadSchema(
                    request_token=upload_request.request_token,
                    uploader_id=create_upload_req.uploader_id,
                )
            )

        # Assert
        assert e.value == BadRequestError("File is not uploaded.")

    @pytest.mark.parametrize(
        "create_upload_req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="file",
                mimetype="a",
                size_bytes=10,
            ),
        ],
    )
    async def test_confirm_upload_with_invalid_size(
        self: Self,
        create_upload_req: CreateUploadRequestSchema,
        file_service: FileService,
    ) -> None:
        """Test claiemd size and actual size mismatch fails."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Mocks
        mock_object_stat = Mock()
        mock_object_stat.size = 888
        file_service._minio.stat_object.return_value = mock_object_stat  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        file_service._minio.presigned_put_object.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        # Reading generated token's content
        upload_request = await file_service.create_upload_request(create_upload_req)

        # Act
        with pytest.raises(BadRequestError) as e:
            await file_service.confirm_upload(
                ConfirmFileUploadSchema(
                    request_token=upload_request.request_token,
                    uploader_id=create_upload_req.uploader_id,
                )
            )

        # Assert
        assert e.value == BadRequestError(
            f"Uploaded file size does not match ({create_upload_req.size_bytes})."
        )

    @pytest.mark.parametrize(
        "create_upload_req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="file",
                mimetype="a",
                size_bytes=10,
            ),
        ],
    )
    async def test_confirm_upload_with_invalid_mimetype(
        self: Self,
        create_upload_req: CreateUploadRequestSchema,
        file_service: FileService,
    ) -> None:
        """Test if claimed mimetype and actual mimetype mismatch fails."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Mocks
        mock_object_stat = Mock()
        mock_object_stat.size = create_upload_req.size_bytes
        file_service._minio.stat_object.return_value = mock_object_stat  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        mock_object_binary = Mock()
        mock_object_binary.read.return_value = b"fake image binary data"
        file_service._minio.get_object.return_value = mock_object_binary  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        file_service._minio.get_presigned_url.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        file_service._minio.presigned_put_object.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        # Reading generated token's content
        upload_request = await file_service.create_upload_request(create_upload_req)

        # Act
        with (
            patch(
                "tvp.files.service.magic.from_buffer",
                return_value="A DIFFERENT MIMETYP",
            ),
            pytest.raises(BadRequestError) as e,
        ):
            await file_service.confirm_upload(
                ConfirmFileUploadSchema(
                    request_token=upload_request.request_token,
                    uploader_id=create_upload_req.uploader_id,
                )
            )

        # Assert
        assert e.value == BadRequestError(
            f"Uploaded file mimetype does not match ({create_upload_req.mimetype})."
        )

    @pytest.mark.parametrize(
        "create_upload_req",
        [
            CreateUploadRequestSchema(
                uploader_id=uuid.uuid4(),
                name="file",
                mimetype="a",
                size_bytes=10,
            ),
        ],
    )
    async def test_confirm_upload_with_already_finalized_upload(
        self: Self,
        create_upload_req: CreateUploadRequestSchema,
        file_service: FileService,
    ) -> None:
        """Test valid token raises bad reqest if file is already inside database."""
        # Arrange
        file_service.ALLOWED_MIMETYPES = ["a", "b"]
        file_service.MAX_FILE_SIZE_BYTES = 1024

        # Mocking
        file_service._minio.presigned_put_object.return_value = "some-url"  # ty:ignore[unresolved-attribute]  # noqa: SLF001

        # Reading generated token's content
        upload_request = await file_service.create_upload_request(create_upload_req)
        token_body = validate_jwt(
            upload_request.request_token, _FileUploadRequestJWTSchema
        )
        assert token_body is not None

        # Create file with the same id in database
        await file_service._file_repo.create(  # noqa: SLF001
            UploadedFile(
                id=UUID(token_body.generated_file_id),
                name=token_body.name,
                mimetype=token_body.mimetype,
                size_bytes=token_body.size_bytes,
                uploader_id=UUID(token_body.uploader_id),
                key=tvp.files.storage_keys.file_upload_key(
                    token_body.mimetype, UUID(token_body.generated_file_id)
                ),
            )
        )

        # Act
        with pytest.raises(BadRequestError) as e:
            await file_service.confirm_upload(
                ConfirmFileUploadSchema(
                    request_token=upload_request.request_token,
                    uploader_id=create_upload_req.uploader_id,
                )
            )

        # Assert
        assert e.value == BadRequestError("File upload request is already finalized.")
