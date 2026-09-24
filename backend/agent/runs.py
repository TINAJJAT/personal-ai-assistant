"""Track and cancel the single active agent run."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4


RunStatus = Literal[
    "running",
    "stopping",
    "completed",
    "cancelled",
    "failed",
]


class RunBusyError(RuntimeError):
    """Another run is still active."""


@dataclass
class RunRecord:
    run_id: str
    thread_id: str
    status: RunStatus = "running"
    task: asyncio.Task[None] | None = None
    error_type: str | None = None

    def public_status(self) -> dict:
        """Return status without exposing task objects or internal errors."""
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "status": self.status,
        }


class RunManager:
    """Manage one active run and retain its latest status in memory."""

    def __init__(self) -> None:
        self._latest: RunRecord | None = None

    def start(
        self,
        thread_id: str,
        operation: Callable[[], Awaitable[None]],
    ) -> RunRecord:
        """Schedule an operation without blocking the API request."""
        previous = self._latest

        if (
            previous is not None
            and previous.task is not None
            and not previous.task.done()
        ):
            raise RunBusyError("The assistant is already processing a request.")

        run = RunRecord(
            run_id=str(uuid4()),
            thread_id=thread_id,
        )

        task = asyncio.create_task(
            self._execute(run, operation),
            name=f"agent-run-{run.run_id}",
        )

        run.task = task
        self._latest = run

        # Handles cancellation before _execute starts.
        task.add_done_callback(
            lambda finished: self._mark_cancelled(run, finished)
        )

        return run

    async def _execute(
        self,
        run: RunRecord,
        operation: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            await operation()

        except asyncio.CancelledError:
            run.status = "cancelled"
            raise

        except Exception as exc:
            run.status = "failed"
            run.error_type = type(exc).__name__

        else:
            run.status = "completed"

    @staticmethod
    def _mark_cancelled(
        run: RunRecord,
        task: asyncio.Task[None],
    ) -> None:
        if task.cancelled():
            run.status = "cancelled"

    def get(self, run_id: str) -> RunRecord | None:
        run = self._latest

        if run is not None and run.run_id == run_id:
            return run

        return None

    def stop(self, run_id: str) -> RunRecord:
        """Request cancellation; cleanup finishes asynchronously."""
        run = self.get(run_id)

        if run is None:
            raise KeyError("Run not found.")

        if (
            run.task is not None
            and not run.task.done()
            and run.status == "running"
        ):
            run.status = "stopping"
            run.task.cancel()

        return run

    async def close(self) -> None:
        """Cancel and await the active run during application shutdown."""
        run = self._latest

        if run is None or run.task is None:
            return

        if not run.task.done():
            self.stop(run.run_id)

        await asyncio.gather(run.task, return_exceptions=True)