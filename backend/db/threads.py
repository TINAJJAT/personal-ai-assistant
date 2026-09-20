"""Async storage for conversation metadata."""

from uuid import uuid4

from psycopg_pool import AsyncConnectionPool


async def create_thread_table(pool: AsyncConnectionPool) -> None:
    """Initialize the conversation metadata table."""
    async with pool.connection() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS chat_threads_updated_idx
            ON chat_threads (updated_at DESC, thread_id DESC)
            """
        )


def validate_title(title: str) -> str:
    """Normalize and validate a conversation title."""
    title = title.strip()

    if not title:
        raise ValueError("Conversation title cannot be empty.")

    if len(title) > 120:
        raise ValueError("Conversation title cannot exceed 120 characters.")

    return title


class ThreadRepository:
    """Read and update conversation metadata using a shared pool."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool

    async def create(self, title: str = "New Chat") -> dict:
        title = validate_title(title)
        thread_id = str(uuid4())

        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO chat_threads (thread_id, title)
                VALUES (%s, %s)
                RETURNING thread_id, title, created_at, updated_at
                """,
                (thread_id, title),
            )
            row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("Conversation creation returned no record.")

        return row

    async def list_recent(self, limit: int = 50) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT thread_id, title, created_at, updated_at
                FROM chat_threads
                ORDER BY updated_at DESC, thread_id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return await cursor.fetchall()

    async def get(self, thread_id: str) -> dict | None:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT thread_id, title, created_at, updated_at
                FROM chat_threads
                WHERE thread_id = %s
                """,
                (thread_id,),
            )
            return await cursor.fetchone()

    async def rename(self, thread_id: str, title: str) -> bool:
        title = validate_title(title)

        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE chat_threads
                SET title = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = %s
                """,
                (title, thread_id),
            )
            return cursor.rowcount == 1

    async def touch(self, thread_id: str) -> bool:
        """Update activity time after a conversation interaction."""
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE chat_threads
                SET updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = %s
                """,
                (thread_id,),
            )
            return cursor.rowcount == 1