"""Request cancellation after receiving the first streamed token."""

import json

import httpx


def main() -> None:
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=httpx.Timeout(120, connect=5),
    ) as client:
        response = client.post(
            "/threads",
            json={"title": "Cancellation check"},
        )
        response.raise_for_status()
        thread_id = response.json()["thread_id"]

        run_id = None
        stop_requested = False
        terminal_event = None

        with client.stream(
            "POST",
            f"/threads/{thread_id}/messages/stream",
            json={
                "message": (
                    "Explain Python async programming in detail, "
                    "with ten examples."
                )
            },
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                event = json.loads(line)
                event_type = event["type"]

                if event_type == "started":
                    run_id = event["run_id"]
                    print("Run:", run_id)

                elif event_type == "token" and not stop_requested:
                    assert run_id is not None

                    stopped = client.post(f"/runs/{run_id}/stop")
                    stopped.raise_for_status()

                    stop_requested = True
                    print("Stop response:", stopped.json()["status"])

                elif event_type in {"done", "cancelled", "error"}:
                    terminal_event = event_type
                    print("Final event:", event_type)

                    if event_type == "error":
                        print(event["message"])

        if run_id is not None:
            status = client.get(f"/runs/{run_id}")
            status.raise_for_status()
            print("Run status:", status.json()["status"])

        if terminal_event == "cancelled":
            print("PASS: cancellation confirmed.")
        elif terminal_event == "done":
            print("The run completed before cancellation took effect.")
        else:
            raise RuntimeError("Cancellation was not confirmed.")


if __name__ == "__main__":
    main()