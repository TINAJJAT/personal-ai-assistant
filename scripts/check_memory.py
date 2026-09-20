"""Check PostgreSQL persistence across separate Python runs."""

import argparse
import asyncio
import sys

import httpx

from backend.config import load_settings
from backend.agent.factory import build_agent
from backend.db.checkpoints import build_checkpointer
from backend.db.connection import open_database_pool
from backend.tools.registry import build_tools


async def main(action: str, thread_id: str) -> None:
    settings = load_settings()

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 10,
    }

    async with open_database_pool(settings) as pool:
        async with httpx.AsyncClient() as client:
            agent = build_agent(
                settings=settings,
                tools=build_tools(settings, client),
                checkpointer=build_checkpointer(pool),
            )

            snapshot = await agent.aget_state(config)
            messages = snapshot.values.get("messages", [])

            if action == "read":
                if not messages:
                    raise RuntimeError(
                        "No saved conversation. Run the write action first."
                    )

                for message in messages:
                    if message.type in {"human", "ai"} and message.content:
                        print(f"{message.type}: {message.content}")

                print("\nSaved conversation loaded from PostgreSQL.")
                return

            if action == "write":
                if messages:
                    raise RuntimeError(
                        "This thread already exists. Use read or ask, "
                        "or provide a different --thread-id."
                    )

                prompt = (
                    "For this conversation, my project codename is "
                    "Blue Lantern. Acknowledge it briefly without tools."
                )

            else:
                if not messages:
                    raise RuntimeError(
                        "No saved conversation. Run the write action first."
                    )

                if snapshot.next:
                    raise RuntimeError(
                        "The previous run is unfinished. "
                        "Use a new test thread for this check."
                    )

                prompt = (
                    "What project codename did I tell you earlier? "
                    "Answer without tools."
                )

            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [{"role": "user", "content": prompt}]},
                    config=config,
                ),
                timeout=90,
            )

            print("Assistant:", result["messages"][-1].content)
            print("Thread:", thread_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["write", "read", "ask"])
    parser.add_argument("--thread-id", default="memory-check-001")
    args = parser.parse_args()

    loop_factory = (
        asyncio.SelectorEventLoop
        if sys.platform == "win32"
        else asyncio.new_event_loop
    )

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(main(args.action, args.thread_id))