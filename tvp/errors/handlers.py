from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from tvp.errors import FieldsError
from tvp.errors.base import APIError


async def handle_apierror(_request: Request, exc: APIError) -> JSONResponse:
    content, status_code = exc.make_response()
    return JSONResponse(content=content, status_code=status_code)


async def handle_pydantic_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: dict[str, list[str]] = {}

    for error in exc.errors():
        # Get the field path (e.g., "user.name" or just "field")
        field = ".".join(
            str(loc) for loc in error["loc"][1:]
        )  # We skip one item to omit location and just get the field name

        message = error["msg"]

        if field not in errors:
            errors[field] = []
        errors[field].append(message)

    content, status_code = FieldsError(errors).make_response()

    return JSONResponse(content=content, status_code=status_code)


EXCEPTION_HANDLERS: dict[
    int | type[Exception], Callable[[Request, Any], Coroutine[Any, Any, Response]]
] = {
    APIError: handle_apierror,
    RequestValidationError: handle_pydantic_validation_error,
}
