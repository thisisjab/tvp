from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from taskiq import Context, TaskiqDepends

from tvp.redis.connection import get_redis

RedisClient = Annotated[Redis, Depends(get_redis)]


async def get_taskiq_redis(
    context: Annotated[Context, TaskiqDepends()],
) -> Redis:
    return context.state.redis


TaskiqRedisClient = Annotated[Redis, TaskiqDepends(get_taskiq_redis)]
