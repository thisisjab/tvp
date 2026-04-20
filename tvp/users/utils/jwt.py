from datetime import datetime

import jwt
import pydantic
import structlog
from pydantic import BaseModel

from tvp import config

logger = structlog.get_logger()


def create_jwt(payload: BaseModel, expires_at: datetime | int) -> str:
    payload = payload.model_dump()
    payload.update({"exp": expires_at})
    return jwt.encode(payload, config.jwt.secret_key, algorithm="HS256")


def validate_jwt[T: BaseModel](token: str, dest: type[T]) -> T | None:
    try:
        data = jwt.decode(token, key=config.jwt.secret_key, algorithms=["HS256"])
        return dest.model_validate(data, extra="ignore")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, pydantic.ValidationError):
        return None
