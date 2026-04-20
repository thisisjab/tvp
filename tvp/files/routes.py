from fastapi import APIRouter

from tvp.files.deps import FileServiceDep
from tvp.files.schemas import (
    ConfirmFileUploadRequest,
    ConfirmFileUploadSchema,
    CreateUploadRequestSchema,
    FileSchema,
    FileUploadRequest,
    FileUploadResponse,
)
from tvp.users.deps import CurrentUserDep

files_router = APIRouter(tags=["Files"])


@files_router.post("/request-upload")
async def request_upload(
    req: FileUploadRequest, file_service: FileServiceDep, user: CurrentUserDep
) -> FileUploadResponse:
    """
    Request upload is used to get a pre-signed upload URL to upload a file directly
    into the bucket. After uploading the file before the expiry, client will notify
    the server for finalizing the upload request.
    """  # noqa: D205
    return await file_service.create_upload_request(
        CreateUploadRequestSchema(**req.model_dump(), uploader_id=user.id)
    )


@files_router.post("/confirm-upload")
async def confirm_upload(
    req: ConfirmFileUploadRequest, file_service: FileServiceDep, user: CurrentUserDep
) -> FileSchema:
    """
    Confirm upload route is used by clients to indicate they have successfully uploaded
    file into the bucket to let server further process the file upload request. Finally
    server will return file and its download url (as a FileSchema).
    """  # noqa: D205
    return await file_service.confirm_upload(
        ConfirmFileUploadSchema(**req.model_dump(), uploader_id=user.id)
    )
