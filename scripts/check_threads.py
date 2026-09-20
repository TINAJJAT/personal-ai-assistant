"""Check conversation metadata storage without calling an LLM."""

import asyncio
import sys

from backend.config import load_settings
from backend.db.connection import open_database_pool
from backend.db.threads import ThreadRepository


async def main() -> None:
    settings = load_settings()

    async with open_database_pool(settings) as pool:
        repository = ThreadRepository(pool)

        thread = await repository.create("Metadata check")
        thread_id = thread["thread_id"]
        print("Created:", thread_id)

        renamed = await repository.rename(
            thread_id,
            "Renamed metadata check",
        )

        if not renamed:
            raise RuntimeError("Conversation rename failed.")

        saved = await repository.get(thread_id)

        if saved is None or saved["title"] != "Renamed metadata check":
            raise RuntimeError("Saved title did not match.")

        print("Loaded:", saved["title"])

        recent = await repository.list_recent(limit=5)
        print("Recent conversations:")

        for item in recent:
            print(f"- {item['title']} ({item['thread_id']})")

        print("\nConversation metadata check passed.")


if __name__ == "__main__":
    loop_factory = (
        asyncio.SelectorEventLoop
        if sys.platform == "win32"
        else asyncio.new_event_loop
    )

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(main())