"""Construct PostgreSQL-backed agent checkpoint storage."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


def build_checkpointer(
    pool: AsyncConnectionPool,
) -> AsyncPostgresSaver:
    """Create a checkpointer using an already-open pool."""
    return AsyncPostgresSaver(pool)