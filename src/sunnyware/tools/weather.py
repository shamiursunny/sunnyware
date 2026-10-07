# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Weather tool — Open-Meteo (free, no API key)."""

import httpx


GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code -> human description
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class WeatherTool:
    name = "weather"
    description = (
        "Get current weather for a city. Returns temperature, wind, "
        "conditions. Uses Open-Meteo (free, no API key)."
    )
    parameters = {
        "city": {
            "type": "string",
            "description": "City name (e.g. 'Dhaka', 'London', 'New York')",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        city = str(args.get("city", "")).strip()
        if not city:
            return {"error": "city is required"}
        if len(city) > 100:
            return {"error": "city name too long"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1) Geocode
                geo_r = await client.get(
                    GEOCODE_URL,
                    params={"name": city, "count": 1, "language": "en", "format": "json"},
                )
                if geo_r.status_code != 200:
                    return {"error": f"geocoding HTTP {geo_r.status_code}"}
                geo = geo_r.json()

                results = geo.get("results") or []
                if not results:
                    return {"error": f"city not found: {city}"}

                place = results[0]
                lat = place["latitude"]
                lon = place["longitude"]
                resolved_name = place.get("name", city)
                country = place.get("country", "")
                admin = place.get("admin1", "")

                # 2) Forecast (current weather)
                w_r = await client.get(
                    FORECAST_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                        "timezone": "auto",
                    },
                )
                if w_r.status_code != 200:
                    return {"error": f"forecast HTTP {w_r.status_code}"}
                w = w_r.json()

                current = w.get("current", {})
                code = current.get("weather_code")

        except Exception as e:
            return {"error": f"weather fetch failed: {type(e).__name__}: {e}"}

        location_parts = [resolved_name]
        if admin and admin != resolved_name:
            location_parts.append(admin)
        if country:
            location_parts.append(country)
        location = ", ".join(location_parts)

        return {
            "location": location,
            "coordinates": {"lat": lat, "lon": lon},
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_kmh": current.get("wind_speed_10m"),
            "conditions": WMO_CODES.get(code, f"code {code}") if code is not None else "unknown",
            "observed_at": current.get("time"),
        }
