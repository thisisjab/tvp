import asyncio
import time
import uuid
from typing import Self

from redis.asyncio import Redis


class RedisLock:
    def __init__(
        self: Self,
        redis: Redis,
        lock_name: str,
        expire_time: int = 10,
        timeout: float = 30,
    ) -> None:
        self._redis = redis
        self.lock_name = f"lock:{lock_name}"
        self.expire_time = expire_time
        self.token = str(uuid.uuid4())
        self.timeout = timeout

    async def acquire(self: Self) -> bool:
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            if await self._redis.set(
                self.lock_name, self.token, nx=True, ex=self.expire_time
            ):
                return True
            await asyncio.sleep(0.01)

        return False

    async def release(self: Self) -> int:
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        result = await self._redis.eval(lua_script, 1, self.lock_name, self.token)  # ty:ignore[invalid-await]

        return int(result) if result else 0

    async def __aenter__(self) -> Self:  # noqa: D105
        if not await self.acquire():
            msg = "Could not acquire lock"
            raise TimeoutError(msg)
        return self

    async def __aexit__(  # noqa: D105
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> bool:
        await self.release()
        return False
