import asyncio
from collections.abc import Generator
from datetime import timedelta
from typing import Self

import anyio
import magic
import minio
import structlog
from minio import Minio, S3Error, ServerError

from tvp import config
from tvp.errors import InternalServerError
from tvp.errors.base import APIError
from tvp.files.schemas import FileObjectInfo, TemporaryUploadUrlSchema
from tvp.utils.datetime import get_now

logger = structlog.getLogger()


class FileService:
    """FileService performs operations related to file storage and retrival."""

    def __init__(
        self: Self,
        minio: Minio,
        bucket: str,
    ) -> None:
        self._minio = minio
        self._bucket = bucket

        self.MAX_FILE_SIZE_BYTES = config.file_upload.max_upload_size_bytes
        self.FILE_UPLOAD_REQUEST_EXPIRY = timedelta(
            seconds=config.file_upload.upload_url_expiry_seconds
        )
        self.DEFAULT_DOWNLOAD_URL_EXPIRY = timedelta(
            seconds=config.file_upload.default_download_url_expiry_seconds
        )

    async def generate_temprary_upload_url(
        self: Self,
        key: str,
        expiry: timedelta | None = None,
    ) -> TemporaryUploadUrlSchema:
        """Generate a pre-signed resumable upload link.

        Client will use given `upload_url` to upload file before expiry. After a
        successful file upload, client will finalize upload by sending back the
        given token. If uploaded file is eqaul to values stored in token, then the
        upload is finalized which means client can use object key to retrieve file
        later.
        """
        expiry = expiry or self.FILE_UPLOAD_REQUEST_EXPIRY
        expires_at = get_now() + expiry

        # Get resumable file upload presigned link
        upload_url = self._minio.presigned_put_object(
            bucket_name=self._bucket,
            object_name=key,
            expires=expiry,
        )

        return TemporaryUploadUrlSchema(
            url=upload_url,
            expires_at=expires_at,
        )

    async def validate_upload(
        self: Self,
        key: str,
        expected_mimetypes: list[str],
        max_size_bytes: int | None = None,
    ) -> None:
        """Check if file is uploaded to storage."""
        # Get object stat from minio to make sure file exists
        try:
            object_stat = self._minio.stat_object(self._bucket, key)
        except minio.error.S3Error as e:
            raise APIError("UPLOADED_FILE_DOES_NOT_EXIST", "") from e  # noqa: EM101

        # Check file size matches
        if object_stat.size is None:
            logger.info("cannot get object size from objcet stat", key=key)
            raise InternalServerError

        max_size_bytes = max_size_bytes or self.MAX_FILE_SIZE_BYTES
        if object_stat.size > max_size_bytes:
            await asyncio.to_thread(self._minio.remove_object(self._bucket, key))
            raise APIError("UPLOADED_FILE_HAS_WRONG_SIZE", "")  # noqa: EM101

        # Get file's first 4 kbytes to validate mimetype
        object_binary = self._minio.get_object(
            self._bucket, key, length=min(object_stat.size, 4 * 1024)
        )

        # Get mimetype
        actual_mimetype = magic.from_buffer(object_binary.read(), mime=True)
        if actual_mimetype not in expected_mimetypes:
            await asyncio.to_thread(self._minio.remove_object(self._bucket, key))
            raise APIError("UPLOADED_FILE_HAS_WRONG_MIMETYPE", "")  # noqa: EM101

    async def get_download_link(
        self: Self, key: str, expiry: timedelta | None = None
    ) -> str:
        """Get temporary download link for a file."""
        expiry = expiry or self.DEFAULT_DOWNLOAD_URL_EXPIRY

        return self._minio.get_presigned_url("GET", self._bucket, key, expires=expiry)

    async def upload_file_from_path(self: Self, key: str, path: str) -> None:
        """Upload file stored in given path in storage with given key."""
        # Validation
        p = anyio.Path(path)
        if not await p.exists():
            raise APIError("FILE_DOES_NOT_EXIST", "")  # noqa: EM101

        if not await p.is_file():
            raise APIError("NOT_VALID_FILE", "")  # noqa: EM101

        mimetype = magic.from_file(path, mime=True)

        # Upload
        await asyncio.to_thread(
            self._minio.fput_object,
            self._bucket,
            key,
            path,
            mimetype,
        )

    async def download_to_path(self: Self, key: str, path: str) -> None:
        """Download given object to given path."""
        try:
            await asyncio.to_thread(self._minio.fget_object, self._bucket, key, path)
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise APIError("NO_SUCH_KEY", "") from e  # noqa: EM101

            logger.exception(
                "unhandled s3 error when downloading to path",
                bucket=self._bucket,
                key=key,
                exc_info=e,
            )
            raise ServerError from e
        except (PermissionError, OSError) as e:
            logger.exception(
                "cannot create file",
                bucket=self._bucket,
                key=key,
                output_path=path,
                exc_info=e,
            )
            raise ServerError from e

    def list_objects(
        self: Self, prefix: str, *, recursive: bool = False
    ) -> Generator[FileObjectInfo]:
        """List objects in given prefix."""
        result = self._minio.list_objects(
            bucket_name=self._bucket,
            prefix=prefix,
            recursive=recursive,
        )

        for r in result:
            yield FileObjectInfo(key=r.key, is_dir=r.is_dir)

    async def upload_dir(self: Self, path: str, prefix: str) -> None:
        """Recursively upload files in given directory to specified prefix."""
        base_path = await anyio.Path(path).resolve()

        async for root, _, files in base_path.walk():
            # Calculate relative path from base directory
            rel_path = str(root.relative_to(base_path))
            if rel_path == ".":
                rel_path = ""

            for f in files:
                # Construct full local file path
                local_file = root / f

                # Construct S3 key
                key = f"{prefix}/{rel_path}/{f}" if rel_path else f"{prefix}/{f}"

                await asyncio.to_thread(
                    self._minio.fput_object,
                    self._bucket,
                    key,
                    str(local_file),
                )
