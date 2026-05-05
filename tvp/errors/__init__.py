from typing import Self

from tvp.errors.base import APIError
from tvp.errors.constants import APIErrorCode


class FieldsError(APIError):
    """FieldsError is used for field validation errors.

    You must pass field errors in this format:

    field_errors: {
        password: [
            "This field must be greater than 8 bytes.",
            "This field must contain special characters.",
        ],
        username: [
            "This username is taken",
        ]
    }
    """

    def __init__(self: Self, field_errors: dict[str, list[str]]) -> None:
        super().__init__(
            APIErrorCode.FIELD_ERROR,
            "Some fields have errors.",
            {"fields": field_errors},
        )


class BadRequestError(APIError):
    def __init__(self: Self, message: str) -> None:
        super().__init__(
            APIErrorCode.BAD_REQUEST,
            message,
        )


class NotFoundError(APIError):
    def __init__(
        self: Self, message: str = "Requested resource was not found."
    ) -> None:
        super().__init__(
            APIErrorCode.NOT_FOUND,
            message,
        )


class InternalServerError(APIError):
    def __init__(self: Self, message: str = "Internal server error.") -> None:
        super().__init__(
            APIErrorCode.SERVER_ERROR,
            message,
        )


class UnathenticatedUserError(APIError):
    def __init__(self: Self, message: str = "Not authenticated.") -> None:
        super().__init__(
            APIErrorCode.UNAUTHORIZED,
            message,
        )
