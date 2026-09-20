"""Manually check hosted model access and tool calling."""

import asyncio

from langchain_core.tools import tool

from backend.config import load_settings
from backend.agent.models import build_primary_model


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


async def main() -> None:
    settings = load_settings()
    model = build_primary_model(settings)
    model_with_tools = model.bind_tools([multiply])

    print(f"Checking: {settings.primary_model}")

    response = await asyncio.wait_for(
        model_with_tools.ainvoke(
            "Use the multiply tool to calculate 12 multiplied by 8."
        ),
        timeout=60,
    )

    if response.invalid_tool_calls:
        raise RuntimeError("The model returned malformed tool arguments.")

    if len(response.tool_calls) != 1:
        raise RuntimeError("Expected exactly one multiply tool call.")

    call = response.tool_calls[0]

    if call["name"] != multiply.name:
        raise RuntimeError("The model selected an unexpected tool.")

    result = multiply.invoke(call["args"])

    if result != 96:
        raise RuntimeError(
            f"The tool call produced {result}; expected 96."
        )

    print("Tool:", call["name"])
    print("Arguments:", call["args"])
    print("Result:", result)
    print("Async inference and tool-call check passed.")


if __name__ == "__main__":
    asyncio.run(main())