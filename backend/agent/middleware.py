"""Controlled retries and safe tool-error handling."""

import httpx
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.tools import BaseTool

from backend.tools.weather import WeatherTemporaryError


def should_retry_model(exc: Exception) -> bool:
    """Retry selected temporary failures, not every exception."""
    if isinstance(
        exc,
        (httpx.TimeoutException, httpx.NetworkError, TimeoutError),
    ):
        return True

    status = getattr(exc, "status_code", None)

    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)

    return status in {408, 500, 502, 503, 504}


def handle_tool_error(
    exc: Exception,
    request: ToolCallRequest,
) -> str | None:
    """Return controlled errors; propagate unexpected exceptions."""
    name = request.tool_call["name"]

    if isinstance(exc, WeatherTemporaryError):
        return (
            "Weather lookup failed after limited retries. "
            "Tell the user it is temporarily unavailable. "
            "Do not immediately repeat this lookup."
        )

    if name == "calculator_tool" and isinstance(exc, ValueError):
        return (
            "The calculation failed. Check that both inputs are finite "
            "numbers, the operation is supported, the divisor is not zero, "
            "and the result fits the supported numeric range."
        )

    if name == "get_weather" and isinstance(exc, (ValueError, RuntimeError)):
        # These exact messages originate in our weather module.
        safe_messages = {
            "Provide a city name.",
            "Weather access was denied. Check the API key and access.",
            "City not found. Provide a city and country code.",
            "Weather rate limit reached. Try again later.",
            "The weather service returned an unexpected response.",
        }

        message = str(exc)

        if message in safe_messages:
            return message

        return "Weather lookup failed. Do not claim weather was retrieved."

    # Leave unexpected failures visible during development.
    return None


def build_middleware(
    tools: list[BaseTool],
) -> list[AgentMiddleware]:
    """Build middleware for the tools actually enabled."""
    middleware: list[AgentMiddleware] = [
        ModelRetryMiddleware(
            max_retries=1,
            retry_on=should_retry_model,
            initial_delay=1,
            backoff_factor=2,
            max_delay=4,
            jitter=True,
            on_failure="error",
        ),
    ]

    enabled_names = {tool.name for tool in tools}

    if "get_weather" in enabled_names:
        middleware.append(
            ToolRetryMiddleware(
                tools=["get_weather"],
                retry_on=(WeatherTemporaryError,),
                max_retries=2,
                initial_delay=1,
                backoff_factor=2,
                max_delay=4,
                jitter=True,
                on_failure="error",
            )
        )

    middleware.append(
        ToolErrorMiddleware(on_error=handle_tool_error)
    )

    return middleware