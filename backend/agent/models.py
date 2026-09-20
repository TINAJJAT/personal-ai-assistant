"""Model factories for the personal assistant."""

from langchain_openrouter import ChatOpenRouter

from backend.config import Settings


def build_model(
    model_name: str,
    settings: Settings,
) -> ChatOpenRouter:
    """Create a model client without making an inference request."""

    return ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,
        temperature=0,
        max_tokens=2048,
        max_retries=0,
    )


def build_primary_model(settings: Settings) -> ChatOpenRouter:
    """Create the model used by the agent."""
    return build_model(settings.primary_model, settings)


def build_summary_model(settings: Settings) -> ChatOpenRouter:
    """Create the model used to summarize conversations."""
    return build_model(settings.summary_model, settings)


def build_fallback_model(
    settings: Settings,
) -> ChatOpenRouter | None:
    """Create a fallback client only when one is configured."""
    if not settings.fallback_model:
        return None

    return build_model(settings.fallback_model, settings)