"""Run the personal assistant API locally."""

import asyncio
import sys

import uvicorn


async def main() -> None:
    config = uvicorn.Config(
        app="backend.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        lifespan="on",
    )

    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    loop_factory = (
        asyncio.SelectorEventLoop
        if sys.platform == "win32"
        else asyncio.new_event_loop
    )

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(main())