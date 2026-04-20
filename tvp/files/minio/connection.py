import minio

from tvp import config

minio_client = minio.Minio(
    endpoint=config.minio.endpoint,
    secure=config.minio.secure,
    access_key=config.minio.access_key,
    secret_key=config.minio.secret_key,
    region=config.minio.region,
)


def get_minio() -> minio.Minio:
    return minio_client
