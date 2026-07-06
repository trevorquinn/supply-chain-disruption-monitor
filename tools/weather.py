"""
Port weather via Open-Meteo — free, no API key required.
Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import httpx

from tools.ports import find_port

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Beaufort scale rough mapping for readability
_WIND_DESCRIPTIONS = [
    (0, "Calm"),
    (1, "Light air"),
    (6, "Light breeze"),
    (12, "Gentle breeze"),
    (20, "Moderate breeze"),
    (29, "Fresh breeze"),
    (39, "Strong breeze"),
    (50, "Near gale"),
    (62, "Gale"),
    (75, "Strong gale"),
    (89, "Storm"),
    (103, "Violent storm"),
    (float("inf"), "Hurricane"),
]


def _wind_description(knots: float) -> str:
    kmh = knots * 1.852
    for threshold, label in _WIND_DESCRIPTIONS:
        if kmh <= threshold:
            return label
    return "Hurricane"


# WMO weather code descriptions
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


async def get_port_weather(port_name: str) -> dict:
    """
    Fetch current weather and 24-hour forecast for a named port.

    Args:
        port_name: Common name or UN/LOCODE of the port (e.g. "Rotterdam", "NLRTM")

    Returns:
        dict with 'port', 'current', and 'forecast_24h' keys
    """
    port = find_port(port_name)
    if not port:
        return {
            "error": f"Port '{port_name}' not found. Use list_major_ports() to see available ports.",
            "port": port_name,
        }

    params = {
        "latitude": port["lat"],
        "longitude": port["lon"],
        "current": [
            "temperature_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "precipitation",
            "weather_code",
            "wave_height",  # available in marine models but gracefully absent here
        ],
        "hourly": [
            "temperature_2m",
            "wind_speed_10m",
            "precipitation_probability",
            "weather_code",
        ],
        "wind_speed_unit": "kn",  # knots — standard maritime
        "forecast_days": 2,
        "timezone": "UTC",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {})

    weather_code = current.get("weather_code", 0)
    wind_kn = current.get("wind_speed_10m", 0)

    # Next 24 hours of hourly forecast (indices 0-23)
    forecast = []
    times = hourly.get("time", [])[:24]
    for i, t in enumerate(times):
        wc = hourly["weather_code"][i] if i < len(hourly.get("weather_code", [])) else 0
        forecast.append(
            {
                "time_utc": t,
                "condition": _WMO_CODES.get(wc, "Unknown"),
                "wind_speed_kn": round(hourly["wind_speed_10m"][i], 1)
                if i < len(hourly.get("wind_speed_10m", []))
                else None,
                "precip_probability_pct": hourly["precipitation_probability"][i]
                if i < len(hourly.get("precipitation_probability", []))
                else None,
            }
        )

    # Assess operational impact
    impact = "Normal"
    if wind_kn > 40:
        impact = "Severe — port operations likely suspended"
    elif wind_kn > 25:
        impact = "Elevated — large vessels may experience delays"
    elif wind_kn > 15:
        impact = "Moderate — watch conditions for heavy cargo"

    return {
        "port": port["name"],
        "locode": port["locode"],
        "country": port["country"],
        "coordinates": {"lat": port["lat"], "lon": port["lon"]},
        "current": {
            "condition": _WMO_CODES.get(weather_code, "Unknown"),
            "temperature_c": current.get("temperature_2m"),
            "wind_speed_kn": round(wind_kn, 1),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "wind_description": _wind_description(wind_kn),
            "precipitation_mm": current.get("precipitation"),
        },
        "operational_impact": impact,
        "forecast_24h": forecast,
    }
