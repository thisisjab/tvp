from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from taskiq import TaskiqDepends

from tvp.redis.connection import get_redis

RedisClient = Annotated[Redis, Depends(get_redis)]
TaskiqRedisClient = Annotated[Redis, TaskiqDepends(get_redis)]
