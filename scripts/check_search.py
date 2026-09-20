"""Manually check async web search without calling an LLM."""

import asyncio

from backend.config import load_settings
from backend.tools.search import create_search_tool


async def main() -> None:
    settings = load_settings()
    search_tool = create_search_tool(settings)

    response = await asyncio.wait_for(
        search_tool.ainvoke({
            "query": "LangGraph persistence official documentation",
        }),
        timeout=30,
    )

    if not isinstance(response, dict):
        raise RuntimeError("Search returned an unexpected response format.")

    if response.get("error"):
        raise RuntimeError(
            "Search failed. Check Tavily credentials and account usage."
        )

    results = response.get("results", [])

    if not results:
        print("Search completed but returned no results.")
        return

    for index, result in enumerate(results, start=1):
        print(f"\n{index}. {result.get('title', 'Untitled')}")
        print(result.get("url", ""))
        print(result.get("content", "")[:300])


if __name__ == "__main__":
    asyncio.run(main())