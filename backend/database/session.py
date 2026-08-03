"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings


def async_database_url(url: str) -> str:
    """Return a SQLAlchemy asyncpg URL from a plain Postgres URL."""

    if url.startswith("postgresql+asyncpg://"):
        converted = url
    elif url.startswith("postgresql://"):
        converted = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        converted = url

    parts = urlsplit(converted)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"sslmode", "channel_binding"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def async_connect_args(url: str) -> dict[str, bool]:
    """Return asyncpg connection args derived from a Postgres URL."""

    query = dict(parse_qsl(urlsplit(url).query))
    if query.get("sslmode") in {"require", "verify-ca", "verify-full"}:
        return {"ssl": True}
    return {}


@lru_cache
def get_async_engine() -> AsyncEngine:
    """Return the application database engine."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return create_async_engine(
        async_database_url(settings.database_url),
        connect_args=async_connect_args(settings.database_url),
        pool_pre_ping=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory."""

    return async_sessionmaker(
        get_async_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield one database session for a request or service operation."""

    async with get_sessionmaker()() as session:
        yield session
