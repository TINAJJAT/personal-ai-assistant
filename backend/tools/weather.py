"""Async tool for current weather."""

import httpx
from langchain_core.tools import BaseTool, tool

from backend.config import Settings


class WeatherTemporaryError(RuntimeError):
    """A temporary weather-service failure."""


def create_weather_tool(
    settings: Settings,
    client: httpx.AsyncClient,
) -> BaseTool:
    """Build the weather tool using an application-owned HTTP client."""
    api_key = (settings.weather_api_key or "").strip()

    if not api_key:
        raise ValueError("WEATHER_API_KEY is missing.")

    @tool
    async def get_weather(city: str) -> dict:
        """Get current weather, not a forecast.

        Specify the city and optionally its country code,
        such as 'Bengaluru,IN' or 'London,GB'.
        """
        city = city.strip()

        if not city:
            raise ValueError("Provide a city name.")

        try:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": city,
                    "appid": api_key,
                    "units": "metric",
                },
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
        except httpx.RequestError:
            # Avoid exposing the request URL, which contains the API key.
            raise WeatherTemporaryError(
                "Could not reach the weather service."
            ) from None

        status = response.status_code

        if status in {401, 403}:
            raise ValueError(
                "Weather access was denied. Check the API key and access."
            )

        if status == 404:
            raise ValueError(
                "City not found. Provide a city and country code."
            )

        if status == 429:
            raise RuntimeError(
                "Weather rate limit reached. Try again later."
            )

        if 500 <= status < 600:
            raise WeatherTemporaryError(
                "The weather service is temporarily unavailable."
            )

        if status != 200:
            raise RuntimeError(
                f"Weather request failed with HTTP status {status}."
            )

        try:
            data = response.json()

            return {
                "city": data["name"],
                "country": data["sys"].get("country"),
                "temperature_c": data["main"]["temp"],
                "feels_like_c": data["main"]["feels_like"],
                "humidity_percent": data["main"]["humidity"],
                "conditions": data["weather"][0]["description"],
                "observed_at_unix": data["dt"],
            }
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError(
                "The weather service returned an unexpected response."
            ) from None

    return get_weather