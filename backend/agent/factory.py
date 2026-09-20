"""Build the personal assistant agent."""

from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.config import Settings
from backend.agent.middleware import build_middleware
from backend.agent.models import build_primary_model
from backend.agent.prompts import SYSTEM_PROMPT


def build_agent(
    settings: Settings,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Create an agent with optional persistent conversation state."""
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Configured user timezone: {settings.timezone}\n"
    )

    return create_agent(
        model=build_primary_model(settings),
        tools=tools,
        system_prompt=prompt,
        middleware=build_middleware(tools),
        checkpointer=checkpointer,
    )