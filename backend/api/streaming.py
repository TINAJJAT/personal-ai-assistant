"""Bridge an NDJSON response stream to a cancellable agent task."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing

from backend.agent.runs import RunBusyError, RunManager

logger = logging.getLogger(__name__)


class StreamFailure(RuntimeError):
    """The source stream did not produce a successful final answer."""


async def managed_stream(
    manager: RunManager,
    thread_id: str,
    source: Callable[[], AsyncIterator[str]],
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=128)
    final_event: str | None = None
    failure_message = (
        "The response could not be completed. Partial progress may be saved."
    )

    def encode(event_type: str, **data) -> str:
        return json.dumps({"type": event_type, **data}) + "\n"

    async def produce() -> None:
        nonlocal final_event, failure_message

        try:
            async with aclosing(source()) as events:
                async for event in events:
                    payload = json.loads(event)

                    if final_event is not None:
                        raise StreamFailure("Received data after completion.")

                    if payload["type"] == "error":
                        failure_message = payload["message"]
                        raise StreamFailure("The source reported failure.")

                    if payload["type"] == "done":
                        final_event = event

                    elif payload["type"] == "token":
                        await queue.put(event)

                    else:
                        raise StreamFailure("Unexpected source event.")

            if final_event is None:
                raise StreamFailure("Missing completion event.")

        except Exception as exc:
            logger.error(
                "Managed stream failed: %s",
                type(exc).__name__,
            )
            raise

    try:
        run = manager.start(thread_id, produce)
    except RunBusyError:
        yield encode(
            "error",
            message="The assistant is busy. Try again later.",
        )
        return

    task = run.task
    assert task is not None

    pending_read: asyncio.Task[str] | None = None

    try:
        yield encode(
            "started",
            run_id=run.run_id,
            thread_id=thread_id,
        )

        while True:
            # Discard buffered tokens after cancellation or failure.
            if task.done() and run.status != "completed":
                break

            if task.done() and queue.empty():
                break

            pending_read = asyncio.create_task(queue.get())

            await asyncio.wait(
                {pending_read, task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if pending_read.done():
                event = pending_read.result()
                pending_read = None

                if run.status not in {"stopping", "cancelled", "failed"}:
                    yield event

            else:
                pending_read.cancel()
                await asyncio.gather(
                    pending_read,
                    return_exceptions=True,
                )
                pending_read = None

        if task.cancelled() or run.status == "cancelled":
            yield encode("cancelled", run_id=run.run_id)

        elif run.status == "completed" and final_event is not None:
            yield final_event

        else:
            yield encode("error", message=failure_message)

    finally:
        # Request cancellation if the streaming client disconnects.
        if not task.done():
            manager.stop(run.run_id)

        if pending_read is not None:
            pending_read.cancel()
            await asyncio.gather(
                pending_read,
                return_exceptions=True,
            )