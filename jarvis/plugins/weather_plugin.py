"""
plugins/weather_plugin.py — Example plugin demonstrating the plugin system.

Install dependency: pip install requests
Get a free API key at https://openweathermap.org/api
Set env var: WEATHER_API_KEY=your_key_here
"""

import os
import urllib.parse
import urllib.request
import json

from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

_API_KEY = os.getenv("WEATHER_API_KEY", "")
_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


@register_command("weather")
def get_weather(city: str) -> str:
    """
    Get current weather for *city*.
    Requires WEATHER_API_KEY environment variable.
    """
    if not city:
        return "Which city's weather would you like to know?"

    if not _API_KEY:
        return (
            "Weather plugin needs a WEATHER_API_KEY environment variable. "
            f"Get one free at openweathermap.org."
        )

    try:
        params = urllib.parse.urlencode({
            "q": city,
            "appid": _API_KEY,
            "units": "metric",
        })
        with urllib.request.urlopen(f"{_BASE_URL}?{params}", timeout=5) as resp:
            data = json.loads(resp.read())

        temp = round(data["main"]["temp"])
        feels_like = round(data["main"]["feels_like"])
        description = data["weather"][0]["description"]
        humidity = data["main"]["humidity"]

        return (
            f"In {city} it is currently {temp}°C, feels like {feels_like}°C. "
            f"Conditions: {description}. Humidity: {humidity}%."
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"I couldn't find weather data for '{city}'."
        return f"Weather service returned an error: {e.code}."
    except Exception as exc:
        log.error("Weather plugin error: %s", exc)
        return "I couldn't retrieve the weather right now."
