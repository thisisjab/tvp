from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FileSchema(BaseModel):
    """FileSchema represents a file stored in file storage service (S3, minio, etc.)."""

    id: UUID
    name: str
    size_bytes: int
    mimetype: str
    url: str

    # Key refers to location of file on disk if local file storage is used,
    # otherwise it refers to object key in the storage (S3, minio).
    key: str

    # Uploader ID refers to user ID of the uploader
    uploader_id: UUID

    created_at: datetime


class FileUploadRequest(BaseModel):  # Used in routes
    """FileUploadRequest defines the schema of request body of clients when getting pre-signed upload URL."""  # noqa: E501

    # Validation of these fields happens in file service
    name: str
    mimetype: str
    size_bytes: int


class CreateUploadRequestSchema(FileUploadRequest):  # Used in service
    """CreateUploadRequestSchema defines an upload request schema for file service.

    When client wants to upload a file, it needs to send its size and mimetype, so server
    can decide if this is an eligible file upload request. With this approach, client
    doesn't need to upload the file, and then get errors related to disallowed mimetype,
    or file_too_big error.
    """  # noqa: E501

    uploader_id: UUID


class FileUploadResponse(BaseModel):
    """FileUploadResponse contains information about upload request."""

    request_token: str
    upload_url: str
    expires_at: datetime


class ConfirmFileUploadSchema(BaseModel):
    """ConfirmFileUploadSchema defines the request body to finalize upload.

    Finalize upload happens after client sends request token for the file that
    has been uploaded into bucket. After receiving id, file service will do
    some validation and save this file record into database as well.
    """

    uploader_id: UUID
    request_token: str


class ConfirmFileUploadRequest(BaseModel):
    """ConfirmFileUploadRequest defines the request body for finalizing file upload.

    Refer to ConfirmFileUploadSchema for more info.
    """

    request_token: str
