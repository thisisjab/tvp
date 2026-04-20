import uuid
from datetime import timedelta
from typing import Self

import magic
import minio
from minio import Minio
from pydantic import BaseModel
from redis.asyncio import Redis

from tvp import config
from tvp.errors import BadRequestError, FieldsError, InternalServerError
from tvp.files import storage_keys
from tvp.files.models import UploadedFile
from tvp.files.repo import FileRepo
from tvp.files.schemas import (
    ConfirmFileUploadSchema,
    CreateUploadRequestSchema,
    FileSchema,
    FileUploadResponse,
)
from tvp.users.utils import create_jwt, validate_jwt
from tvp.utils.datetime import get_now


class _FileUploadRequestJWTSchema(BaseModel):
    generated_file_id: str
    uploader_id: str
    name: str
    mimetype: str
    size_bytes: int


class FileService:
    """FileService performs operations related to file storage and retrival."""

    def __init__(
        self: Self,
        file_repo: FileRepo,
        redis: Redis,
        minio: Minio,
        bucket: str,
    ) -> None:
        self._file_repo = file_repo
        self._redis = redis
        self._minio = minio
        self._bucket = bucket

        self.MAX_FILE_SIZE_BYTES = config.file_upload.max_upload_size_bytes
        self.ALLOWED_MIMETYPES: list[str] = config.file_upload.allowed_mimetypes
        self.FILE_UPLOAD_REQUEST_EXPIRY = timedelta(
            seconds=config.file_upload.upload_url_expiry_seconds
        )

    async def create_upload_request(
        self: Self, req: CreateUploadRequestSchema
    ) -> FileUploadResponse:
        """Validate upload request and generate a pre-signed resumable upload link.

        Client will use given `upload_url` to upload file before expiry. Then it will
        notify file service (using `file_id`) that upload is finalized in client-side
        so that file service can confirm upload.
        """
        # Validation in advance so that client doesn't need uploading if some rule
        # is voiolated
        if req.size_bytes > self.MAX_FILE_SIZE_BYTES:
            raise FieldsError(
                {
                    "size_bytes": [
                        f"Upload size_bytes cannot be greater than {self.MAX_FILE_SIZE_BYTES}."  # noqa: E501
                    ]
                }
            )

        if req.mimetype not in self.ALLOWED_MIMETYPES:
            raise FieldsError({"mimetype": ["This mimetype is not allowed."]})

        # Generate upload request id
        generated_file_id = uuid.uuid4()

        # Create token
        expires_at = get_now() + self.FILE_UPLOAD_REQUEST_EXPIRY
        request_token = create_jwt(
            _FileUploadRequestJWTSchema(
                generated_file_id=str(generated_file_id),
                uploader_id=str(req.uploader_id),
                mimetype=req.mimetype,
                size_bytes=req.size_bytes,
                name=req.name,
            ),
            expires_at,
        )

        # Get resumable file upload presigned link
        object_key = storage_keys.file_upload_key(
            req.mimetype,
            generated_file_id,
        )
        upload_url = self._minio.presigned_put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            expires=self.FILE_UPLOAD_REQUEST_EXPIRY,
        )

        return FileUploadResponse(
            request_token=request_token,
            expires_at=expires_at,
            upload_url=upload_url,
        )

    async def confirm_upload(
        self: Self,
        req: ConfirmFileUploadSchema,
    ) -> FileSchema:
        """Check if uploaded file in minio has the properties (size, mimetype) that client claimed."""  # noqa: E501
        # Validate token
        data = validate_jwt(req.request_token, _FileUploadRequestJWTSchema)
        if data is None:
            msg = "Request token is invalid."
            raise BadRequestError(msg)

        # Generate object key
        object_key = storage_keys.file_upload_key(
            data.mimetype, uuid.UUID(data.generated_file_id)
        )

        # Get object stat from minio to make sure file exists
        try:
            object_stat = self._minio.stat_object(self._bucket, object_key)
        except minio.error.S3Error as e:
            msg = "File is not uploaded."
            raise BadRequestError(msg) from e

        # Check file size matches
        if object_stat.size is None:
            raise InternalServerError

        if object_stat.size != data.size_bytes:
            msg = f"Uploaded file size does not match ({data.size_bytes})."
            raise BadRequestError(msg)

        # Get file's first 4 kbytes to validate mimetype
        object_binary = self._minio.get_object(
            self._bucket, object_key, length=min(object_stat.size, 4 * 1024)
        )

        # Get mimetype
        actual_mimetype = magic.from_buffer(object_binary.read(), mime=True)
        if actual_mimetype != data.mimetype:
            msg = f"Uploaded file mimetype does not match ({data.mimetype})."
            raise BadRequestError(msg)

        # Save to database
        file = await self._file_repo.create(
            UploadedFile(
                id=uuid.UUID(data.generated_file_id),
                key=object_key,
                name=data.name,
                size_bytes=object_stat.size,
                mimetype=actual_mimetype,
                uploader_id=req.uploader_id,
            )
        )

        return FileSchema.model_validate(file, from_attributes=True)
