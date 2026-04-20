from redis.asyncio import Redis

from tvp import config

redis_client = Redis(
    host=config.redis.host,
    port=config.redis.port,
    db=config.redis.db,
    password=config.redis.password,
    encoding=config.redis.encoding,
    decode_responses=config.redis.decode_responses,
    protocol=2,
)


def get_redis() -> Redis:
    """Get singleton redis client."""
    return redis_client
