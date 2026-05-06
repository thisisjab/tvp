import typing

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker
from taskiq import (
    SmartRetryMiddleware,
    TaskiqEvents,
    TaskiqMessage,
    TaskiqMiddleware,
    TaskiqState,
)
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from tvp import config
from tvp.database.connection import engine
from tvp.files.minio.connection import get_minio
from tvp.redis.connection import get_redis


class StructlogMiddleware(TaskiqMiddleware):
    def pre_send(
        self,
        message: TaskiqMessage,
    ) -> TaskiqMessage | typing.Coroutine[typing.Any, typing.Any, TaskiqMessage]:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            taskiq_task_id=message.task_id, taskiq_task_name=message.task_name
        )

        return message


broker = (
    AioPikaBroker(
        config.broker.address,
    )
    .with_result_backend(RedisAsyncResultBackend(config.broker.result_backend))
    .with_middlewares(
        StructlogMiddleware(),
        SmartRetryMiddleware(
            default_retry_count=5,
            default_delay=10,
            use_jitter=True,
            use_delay_exponent=True,
            max_delay_exponent=120,
        ),
    )
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    state.minio = get_minio()
    state.redis = get_redis()
    state.session_maker = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
