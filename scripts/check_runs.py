"""Check run cancellation without external services."""

import asyncio

from backend.agent.runs import RunBusyError, RunManager


async def main() -> None:
    manager = RunManager()

    started = asyncio.Event()
    cleaned_up = asyncio.Event()
    wait_forever = asyncio.Event()

    async def operation() -> None:
        started.set()

        try:
            await wait_forever.wait()
        finally:
            cleaned_up.set()

    try:
        run = manager.start(
            thread_id="cancellation-check",
            operation=operation,
        )

        await asyncio.wait_for(started.wait(), timeout=2)

        # A second run must be rejected while the first is active.
        try:
            manager.start("another-thread", operation)
        except RunBusyError:
            print("Concurrent run correctly rejected.")
        else:
            raise AssertionError("A second active run was allowed.")

        manager.stop(run.run_id)
        await manager.close()

        assert run.status == "cancelled"
        assert cleaned_up.is_set()

        print("Cancellation completed and cleanup executed.")

        # Confirm that another run can start afterward.
        async def quick_operation() -> None:
            return

        next_run = manager.start(
            thread_id="second-check",
            operation=quick_operation,
        )

        assert next_run.task is not None
        await next_run.task

        assert next_run.status == "completed"

        # An old Stop request must not cancel the newer run.
        try:
            manager.stop(run.run_id)
        except KeyError:
            print("Stale Stop request correctly rejected.")
        else:
            raise AssertionError("An old run ID was accepted.")

        print("Run manager checks passed.")

    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())