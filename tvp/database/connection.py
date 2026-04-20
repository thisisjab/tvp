from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tvp import config

engine = create_async_engine(
    url=config.postgres.database_url,
    pool_pre_ping=True,
    echo=config.postgres.echo,
)

session_maker = async_sessionmaker(
    bind=engine,
    expire_on_commit=True,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Get a session from postgres async session maker."""
    async with session_maker() as session:
        yield session
