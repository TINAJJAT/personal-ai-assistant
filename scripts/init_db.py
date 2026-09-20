"""Initialize LangGraph checkpoint tables in an existing database."""

import asyncio
import sys

from backend.config import load_settings
from backend.db.connection import open_database_pool
from backend.db.checkpoints import build_checkpointer
from backend.db.threads import create_thread_table


async def main() -> None:
    settings = load_settings()

    async with open_database_pool(settings) as pool:
        # Verify connectivity without displaying the connection string.
        async with pool.connection() as connection:
            cursor = await connection.execute("SELECT 1 AS connected")
            row = await cursor.fetchone()

            if row is None or row["connected"] != 1:
                raise RuntimeError("Database connectivity check failed.")

        checkpointer = build_checkpointer(pool)
        await checkpointer.setup()

        await create_thread_table(pool)
        print("Conversation metadata table initialized.")

        print("Database connection successful.")
        print("LangGraph checkpoint tables initialized.")


if __name__ == "__main__":
    # Psycopg async connections require a selector loop on Windows.
    loop_factory = (
        asyncio.SelectorEventLoop
        if sys.platform == "win32"
        else asyncio.new_event_loop
    )

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(main())