from enum import Enum

from fastapi import status


class APIErrorCode(Enum):
    BAD_REQUEST = status.HTTP_400_BAD_REQUEST
    FIELD_ERROR = status.HTTP_422_UNPROCESSABLE_CONTENT
    SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR
    UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
