"""HTTP communication with the local assistant backend."""

import httpx
import json

class APIError(RuntimeError):
    """An API failure that can be displayed to the user."""


class AssistantAPI:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise APIError(
                "The request timed out. Refresh the conversation before "
                "sending again; the backend may still have saved progress."
            ) from None
        except httpx.RequestError:
            raise APIError(
                "Could not reach the backend. Check that it is running."
            ) from None

        if response.is_error:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None

            message = (
                detail
                if isinstance(detail, str)
                else f"Request failed with HTTP status {response.status_code}."
            )
            raise APIError(message)

        try:
            return response.json()
        except ValueError:
            raise APIError("The backend returned an invalid response.") from None

    def list_threads(self) -> list[dict]:
        return self._request("GET", "/threads", params={"limit": 100})

    def create_thread(self, title: str = "New Chat") -> dict:
        return self._request("POST", "/threads", json={"title": title})

    def get_history(self, thread_id: str) -> dict:
        return self._request("GET", f"/threads/{thread_id}/messages")

    def send_message(self, thread_id: str, message: str) -> dict:
        return self._request(
            "POST",
            f"/threads/{thread_id}/messages",
            json={"message": message},
        )

    def stream_message(self, thread_id: str, message: str):
        """Yield stream events and require an explicit completion signal."""
        try:
            with self.client.stream(
                "POST",
                f"/threads/{thread_id}/messages/stream",
                json={"message": message},
            ) as response:
                if response.is_error:
                    response.read()

                    try:
                        detail = response.json().get("detail")
                    except (ValueError, AttributeError):
                        detail = None

                    raise APIError(
                        detail
                        if isinstance(detail, str)
                        else f"Request failed: HTTP {response.status_code}."
                    )

                for line in response.iter_lines():
                    if not line.strip():
                        continue

                    try:
                        event = json.loads(line)
                    except ValueError:
                        raise APIError("Received invalid stream data.") from None

                    if not isinstance(event, dict):
                        raise APIError("Received an invalid stream event.")

                    event_type = event.get("type")

                    if event_type == "error":
                        raise APIError(
                            event.get("message", "The stream failed.")
                        )

                    if event_type == "token":
                        if not isinstance(event.get("text"), str):
                            raise APIError("Received an invalid text event.")

                        yield event

                    elif event_type == "done":
                        if not isinstance(event.get("answer"), str):
                            raise APIError("Received an invalid final answer.")

                        yield event
                        return

                    else:
                        raise APIError("Received an unknown stream event.")

                raise APIError(
                    "The connection ended before completion was confirmed. "
                    "Refresh the conversation before sending again."
                )

        except httpx.TimeoutException:
            raise APIError(
                "The stream timed out. Refresh to inspect saved progress."
            ) from None

        except httpx.RequestError:
            raise APIError(
                "The connection was interrupted. "
                "Refresh to inspect saved progress."
            ) from None