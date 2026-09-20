"""Load application settings without opening external connections."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


# Resolve paths from this file, independent of the terminal directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Existing environment variables take precedence over .env.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def get_required_env(name: str) -> str:
    """Read a required setting without exposing its value in errors."""
    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(
            f"{name} is missing. Set it in your environment or root .env file."
        )

    return value


def get_bool_env(name: str, default: bool = False) -> bool:
    """Parse a boolean setting and reject invalid values."""
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    raise ValueError(f"{name} must be true or false.")


@dataclass(frozen=True)
class Settings:
    """Application settings; secret values are excluded from repr."""

    openrouter_api_key: str = field(repr=False)
    database_url: str = field(repr=False)

    primary_model: str
    summary_model: str
    fallback_model: str | None

    tavily_api_key: str | None = field(repr=False)
    weather_api_key: str | None = field(repr=False)
    youtube_api_key: str | None = field(repr=False)

    timezone: str
    enable_local_tools: bool


def load_settings() -> Settings:
    """Validate configuration when application startup requests it."""
    primary_model = get_required_env("PRIMARY_MODEL")
    summary_model = (
        os.getenv("SUMMARY_MODEL", "").strip() or primary_model
    )
    fallback_model = (
        os.getenv("FALLBACK_MODEL", "").strip() or None
    )

    # Project policy: allow only explicitly free OpenRouter variants.
    # This does not guarantee endpoint availability or tool support.
    # for model in (primary_model, summary_model, fallback_model):
    #     if model and not model.endswith(":free"):
    #         raise ValueError(
    #             "Configured models must use an explicit ':free' variant."
    #         )

    return Settings(
        openrouter_api_key=get_required_env("OPENROUTER_API_KEY"),
        database_url=get_required_env("DATABASE_URL"),
        primary_model=primary_model,
        summary_model=summary_model,
        fallback_model=fallback_model,
        tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
        weather_api_key=os.getenv("WEATHER_API_KEY") or None,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
        timezone=os.getenv("USER_TIMEZONE", "Asia/Kolkata"),
        enable_local_tools=get_bool_env("ENABLE_LOCAL_TOOLS"),
    )