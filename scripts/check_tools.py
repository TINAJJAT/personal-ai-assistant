"""Check tool registration without external API requests."""

import asyncio

import httpx

from backend.config import load_settings
from backend.tools.registry import build_tools


async def main() -> None:
    settings = load_settings()

    async with httpx.AsyncClient() as client:
        tools = build_tools(settings, client)

        names = [tool.name for tool in tools]

        if len(names) != len(set(names)):
            raise ValueError("Tool names must be unique.")

        print("Enabled tools:")

        for tool in tools:
            print(f"- {tool.name}")

        calculator = next(
            tool for tool in tools
            if tool.name == "calculator_tool"
        )

        result = calculator.invoke({
            "a": 12,
            "b": 8,
            "operation": "multiply",
        })

        assert result == 96
        print(f"\nCalculator check passed: {result}")


if __name__ == "__main__":
    asyncio.run(main())