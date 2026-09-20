"""Manually check the weather tool without calling an LLM."""

import asyncio
import json

import httpx

from backend.config import load_settings
from backend.tools.weather import create_weather_tool


async def main() -> None:
    settings = load_settings()

    async with httpx.AsyncClient() as client:
        weather_tool = create_weather_tool(settings, client)

        result = await asyncio.wait_for(
            weather_tool.ainvoke({"city": "Bengaluru,IN"}),
            timeout=20,
        )

        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())