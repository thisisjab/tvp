from typing import Any, Self

import structlog
from fastapi import status

from tvp.errors.constants import APIErrorCode

logger = structlog.getLogger()


class APIError(Exception):
    def __init__(
        self: Self,
        code: APIErrorCode | str,
        message: str,
        metadata: Any | None = None,  # noqa: ANN401 # TODO: fix me after getting internet connection
    ) -> None:
        """Create an API error that can be handled by our custom error handlers."""
        self.message = message
        self.code = code
        self.metadata = metadata

        super().__init__(message)

    def make_response(self: Self) -> tuple[dict[str, Any], int]:
        """Make response generates response dictionary and http status code which can be used in routes and error handlers."""  # noqa: E501
        response = {
            "code": self.code.name.lower()
            if isinstance(self.code, APIErrorCode)
            else self.code.lower(),
            "message": self.message,
        }

        if self.metadata:
            response["metadata"] = self.metadata

        if isinstance(self.code, str):
            logger.error(
                "attempt to make response for non public api error",
                message=self.message,
                code=self.code,
                metadata=self.metadata,
            )
            return {
                "message": "Internal server error.",
                "code": "internal_server_error",
            }, status.HTTP_500_INTERNAL_SERVER_ERROR

        return response, self.code.value

    def __eq__(self: Self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, APIError):
            return False

        return (
            self.code == other.code
            and self.message == other.message
            and self.metadata == other.metadata
        )

    def __hash__(self: Self) -> int:  # noqa: D105
        return hash(frozenset({self.code, self.message, self.metadata}))
