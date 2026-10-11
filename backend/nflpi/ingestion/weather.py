"""Open-Meteo forecasts for outdoor (or retractable-roof) games in the next 7 days.

Coordinates are city-level (two decimals), entered by hand. Weather at that
precision is the same as at the exact stadium.
"""

from datetime import datetime, timedelta

import httpx

from nflpi.config import get_settings

SOURCE = "open-meteo"

STADIUMS: dict[str, tuple[float, float]] = {
    "ATL97": (33.76, -84.40),
    "BAL00": (39.28, -76.62),
    "BOS00": (42.09, -71.26),
    "BUF00": (42.77, -78.79),
    "CAR00": (35.23, -80.85),
    "CHI98": (41.86, -87.62),
    "CIN00": (39.10, -84.52),
    "CLE00": (41.51, -81.70),
    "DAL00": (32.75, -97.09),
    "DEN00": (39.74, -105.02),
    "DET00": (42.34, -83.05),
    "GNB00": (44.50, -88.06),
    "HOU00": (29.68, -95.41),
    "IND00": (39.76, -86.16),
    "JAX00": (30.32, -81.64),
    "KAN00": (39.05, -94.48),
    "LAX01": (33.95, -118.34),
    "MIA00": (25.96, -80.24),
    "MIN01": (44.97, -93.26),
    "NAS00": (36.17, -86.77),
    "NOR00": (29.95, -90.08),
    "NYC01": (40.81, -74.07),
    "PHI00": (39.90, -75.17),
    "PHO00": (33.53, -112.26),
    "PIT00": (40.45, -80.02),
    "SEA00": (47.60, -122.33),
    "SFO01": (37.40, -121.97),
    "TAM00": (27.98, -82.50),
    "VEG00": (36.09, -115.18),
    "WAS00": (38.91, -76.86),
    "LON00": (51.56, -0.28),
    "LON02": (51.60, -0.07),
    "GER00": (48.22, 11.62),
    "MUN01": (48.22, 11.62),
    "MEX00": (19.30, -99.15),
    "MAD01": (40.45, -3.69),
    "MEL00": (-37.82, 144.98),
    "PAR00": (48.92, 2.36),
    "RIO00": (-22.91, -43.23),
    "SAO00": (-23.55, -46.47),
}

# Retractable roofs: roof status is only known on game day, so forecast anyway.
RETRACTABLE = {"ATL97", "DAL00", "HOU00", "IND00", "PHO00"}


def needs_forecast(roof: str | None, stadium_id: str | None) -> bool:
    if stadium_id not in STADIUMS:
        return False
    return roof in ("outdoors", "open", None) or stadium_id in RETRACTABLE


def fetch_forecast(stadium_id: str, kickoff_utc: datetime) -> dict | None:
    """Return conditions for the kickoff hour, or None if outside the forecast window."""
    settings = get_settings()
    lat, lon = STADIUMS[stadium_id]
    day = kickoff_utc.date()
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation_probability,precipitation",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "start_date": day.isoformat(),
        "end_date": (day + timedelta(days=1)).isoformat(),
    }
    resp = httpx.get(settings.open_meteo_url, params=params, timeout=settings.http_timeout_s)
    resp.raise_for_status()
    return pick_kickoff_hour(resp.json(), kickoff_utc)


def pick_kickoff_hour(payload: dict, kickoff_utc: datetime) -> dict | None:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    target = kickoff_utc.strftime("%Y-%m-%dT%H:00")
    if target not in times:
        return None
    i = times.index(target)

    def val(key: str) -> float | None:
        series = hourly.get(key) or []
        return series[i] if i < len(series) else None

    return {
        "temp_f": val("temperature_2m"),
        "wind_mph": val("wind_speed_10m"),
        "gust_mph": val("wind_gusts_10m"),
        "precip_prob": val("precipitation_probability"),
        "precip_in": val("precipitation"),
    }
