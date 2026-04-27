import uuid
from typing import Self

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FileUploadConfiguration(BaseSettings):
    default_download_url_expiry_seconds: int = Field(
        default=60 * 3600  # 60 minutes
    )
    upload_url_expiry_seconds: int = Field(
        default=15 * 3600  # 15 minutes
    )
    max_upload_size_bytes: int = Field(
        default=5 * (1024**3)  # 5 Gbytes
    )

    allowed_mimetypes: list[str] = Field(
        default=[
            # Images
            "image/png",
            "image/jpg",
            "image/jpeg",
            "image/webp",
            # Videos
            "video/mp4",
            "video/mkv",
        ]
    )


class JWTConifugration(BaseSettings):
    auth_token_expiry_seconds: int = Field(default=24 * 60 * 60)  # 24 hours
    secret_key: str = Field(default=str(uuid.uuid4()), min_length=32)


class MinioConfiguration(BaseSettings):
    endpoint: str = Field(default="")
    access_key: str = Field(default="")
    secret_key: str = Field(default="")
    bucket_name: str = Field(default="")
    secure: bool = Field(default=True)
    region: str = Field(default="us-east-1")


class RedisConfiguration(BaseSettings):
    host: str = Field(default="")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    test_db: int = Field(default=15)
    password: str | None = Field(default=None)
    encoding: str = Field(default="utf-8")
    decode_responses: bool = Field(default=True)


class PostgresDatabaseConfiguration(BaseSettings):
    host: str = Field(default="")
    port: int = Field(default=5432)
    user: str = Field(default="postgres")
    password: str = Field(default="password")
    db: str = Field(default="postgres")
    secure: bool = Field(default=True)
    echo: bool = Field(default=False)

    @property
    def database_url(self: Self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def test_database_url(self: Self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/test_{self.db}"


class ServerConfiguration(BaseSettings):
    file_upload: FileUploadConfiguration = Field(default=FileUploadConfiguration())
    jwt: JWTConifugration = Field(default=JWTConifugration())
    minio: MinioConfiguration = Field(default=MinioConfiguration())
    postgres: PostgresDatabaseConfiguration = Field(
        default=PostgresDatabaseConfiguration()
    )
    redis: RedisConfiguration = Field(default=RedisConfiguration())
    listen_ip: str = Field(default="127.0.0.1")
    listen_port: int = Field(default=8000)
    debug_mode: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix="TVP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter=".",
        frozen=True,
    )


server_configuration = ServerConfiguration()
