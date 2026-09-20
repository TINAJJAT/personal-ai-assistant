"""Factory for the Tavily web-search tool."""

from langchain_tavily import TavilySearch

from backend.config import Settings


def create_search_tool(settings: Settings) -> TavilySearch:
    """Create a web-search tool after validating configuration."""
    if not (settings.tavily_api_key or "").strip():
        raise ValueError("TAVILY_API_KEY is missing.")

    # Tavily reads TAVILY_API_KEY from the environment,
    # which backend.config loads from .env.
    return TavilySearch(
        max_results=5,
        topic="general",
        search_depth="basic",
        include_answer=False,
        include_raw_content=False,
        include_images=False,
    )