"""Manage the application's async PostgreSQL connection pool."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from backend.config import Settings


@asynccontextmanager
async def open_database_pool(
    settings: Settings,
) -> AsyncIterator[AsyncConnectionPool]:
    """Open a pool and close it when the application exits."""
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=5,
        timeout=10,
        open=False,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "connect_timeout": 10,
        },
    )

    try:
        await pool.open()
        await pool.wait(timeout=15)
        yield pool
    finally:
        await pool.close()