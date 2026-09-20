"""Assemble the tools enabled for this application."""

import httpx
from langchain_core.tools import BaseTool

from backend.config import Settings
from backend.tools.calculator import calculator_tool
from backend.tools.search import create_search_tool
from backend.tools.weather import create_weather_tool


def build_tools(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> list[BaseTool]:
    """Build tools using application settings and a shared HTTP client."""
    tools: list[BaseTool] = [calculator_tool]

    if (settings.weather_api_key or "").strip():
        tools.append(create_weather_tool(settings, http_client))

    if (settings.tavily_api_key or "").strip():
        tools.append(create_search_tool(settings))

    return tools