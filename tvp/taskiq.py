from taskiq import TaskiqEvents, TaskiqState
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from tvp import config
from tvp.database.connection import get_db
from tvp.files.minio.connection import get_minio
from tvp.redis.connection import get_redis

broker = AioPikaBroker(
    config.broker.address,
).with_result_backend(RedisAsyncResultBackend(config.broker.result_backend))


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    state.minio = get_minio()
    state.redis = get_redis()
    state.get_db = get_db
