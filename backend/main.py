"""Local API application for the personal assistant."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncio

import httpx
from fastapi import FastAPI

from backend.config import load_settings
from backend.agent.factory import build_agent
from backend.db.checkpoints import build_checkpointer
from backend.db.connection import open_database_pool
from backend.db.threads import ThreadRepository
from backend.tools.registry import build_tools
from backend.api.threads import router as threads_router
from backend.api.chat import router as chat_router
from backend.api.recovery import router as recovery_router
from backend.agent.runs import RunManager
from backend.api.runs import router as runs_router

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources and close them during shutdown."""
    settings = load_settings()

    async with open_database_pool(settings) as pool:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
        ) as http_client:
            threads = ThreadRepository(pool)

            # Verify that the metadata table is initialized.
            await threads.list_recent(limit=1)

            checkpointer = build_checkpointer(pool)
            tools = build_tools(settings, http_client)

            app.state.threads = threads
            app.state.agent = build_agent(
                settings=settings,
                tools=tools,
                checkpointer=checkpointer,
            )
            app.state.tool_names = [tool.name for tool in tools]

            app.state.agent_lock = asyncio.Lock()

            runs = RunManager()
            app.state.runs = runs

            try:
                yield
            finally:
                try:
                    # Stop active execution before shared resources close.
                    await runs.close()
                finally:
                    # Release references before closing shared resources.
                    app.state.runs = None
                    app.state.agent = None
                    app.state.threads = None
                    app.state.tool_names = []


app = FastAPI(
    title="Personal AI Assistant",
    description="Local backend for my personal productivity assistant.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(threads_router)
app.include_router(chat_router)
app.include_router(recovery_router)
app.include_router(runs_router)

@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Confirm that the API process is serving requests."""
    return {"status": "ok"}