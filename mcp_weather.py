"""
VoyageReady AI — MCP Weather Tool Server
Exposes a `check_weather` tool via MCP stdio transport.
Uses the free Open-Meteo API (no API key required).
"""
from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("VoyageReady Weather")

# WMO Weather Interpretation Codes → human-readable
_WMO_CODES = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Depositing rime fog 🌫️",
    51: "Light drizzle 🌦️", 53: "Moderate drizzle 🌦️", 55: "Dense drizzle 🌧️",
    56: "Light freezing drizzle 🌧️", 57: "Dense freezing drizzle 🌧️",
    61: "Slight rain 🌧️", 63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️",
    66: "Light freezing rain 🧊", 67: "Heavy freezing rain 🧊",
    71: "Slight snow ❄️", 73: "Moderate snow 🌨️", 75: "Heavy snow 🌨️",
    77: "Snow grains ❄️",
    80: "Slight rain showers 🌦️", 81: "Moderate rain showers 🌧️", 82: "Violent rain showers ⛈️",
    85: "Slight snow showers 🌨️", 86: "Heavy snow showers 🌨️",
    95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️",
    99: "Thunderstorm with heavy hail ⛈️",
}


@mcp.tool()
async def check_weather(city: str, date: str) -> str:
    """Check the weather forecast for a city on a specific date.

    Args:
        city: City name, e.g. "Tokyo", "Paris", "New York"
        date: Date in YYYY-MM-DD format (up to 16 days ahead for forecasts,
              or any past date for historical weather)
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Geocode the city
        geo_resp = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en"},
        )
        geo_data = geo_resp.json()
        results = geo_data.get("results")
        if not results:
            return f"❌ Could not find location: '{city}'. Please check the city name."

        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        loc_name = loc.get("name", city)
        country = loc.get("country", "")

        # 2. Try forecast API first (works for ±16 days from today)
        weather_resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum,precipitation_probability_max,"
                    "weathercode,wind_speed_10m_max,"
                    "uv_index_max"
                ),
                "timezone": "auto",
                "start_date": date,
                "end_date": date,
            },
        )
        data = weather_resp.json()

        # If forecast API doesn't cover the date, try historical archive
        if "error" in data or not data.get("daily", {}).get("time"):
            weather_resp = await client.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": lat, "longitude": lon,
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,weathercode,"
                        "wind_speed_10m_max"
                    ),
                    "timezone": "auto",
                    "start_date": date,
                    "end_date": date,
                },
            )
            data = weather_resp.json()

        daily = data.get("daily", {})
        if not daily.get("time"):
            return (
                f"⚠️ No weather data available for {loc_name} on {date}. "
                f"Forecasts cover up to ~16 days ahead; historical data may "
                f"not be available for all dates."
            )

        # 3. Format the response
        t_max = daily.get("temperature_2m_max", [None])[0]
        t_min = daily.get("temperature_2m_min", [None])[0]
        precip = daily.get("precipitation_sum", [None])[0]
        precip_prob = daily.get("precipitation_probability_max", [None])[0]
        wcode = daily.get("weathercode", [None])[0]
        wind = daily.get("wind_speed_10m_max", [None])[0]
        uv = daily.get("uv_index_max", [None])[0]

        condition = _WMO_CODES.get(wcode, f"Code {wcode}") if wcode is not None else "Unknown"

        lines = [
            f"📍 **{loc_name}, {country}** — {date}",
            f"🌡️ Temperature: {t_min}°C → {t_max}°C" if t_min is not None else None,
            f"🌤️ Condition: {condition}",
            f"🌧️ Precipitation: {precip} mm" if precip is not None else None,
            f"☔ Rain probability: {precip_prob}%" if precip_prob is not None else None,
            f"💨 Max wind: {wind} km/h" if wind is not None else None,
            f"☀️ UV index: {uv}" if uv is not None else None,
        ]
        return "\n".join(line for line in lines if line)


if __name__ == "__main__":
    mcp.run()
