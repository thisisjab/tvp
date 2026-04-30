from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from tvp import config

broker = AioPikaBroker(
    config.broker.address,
).with_result_backend(RedisAsyncResultBackend(config.broker.result_backend))
