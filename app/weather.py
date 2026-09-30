"""City weather lookup, plus Bangalore temperature logging into a note."""

from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import Note, NoteCreate, NoteUpdate, WeatherReport
from app.store import store

NOTE_TITLE = "Current temperature"
NOTE_TAGS = ["weather", "bangalore", "auto"]
BANGALORE_LAT = 12.9716
BANGALORE_LON = 77.5946
IST = ZoneInfo("Asia/Kolkata")
MAX_BODY = 7500
HEADER = "Bangalore temperature log (°C, Asia/Kolkata)"


class CityNotFound(Exception):
    def __init__(self, city: str) -> None:
        super().__init__(f"City not found: {city}")
        self.city = city


def _get_json(url: str) -> dict:
    # Prefer curl on macOS when the system Python CA store is incomplete.
    try:
        raw = subprocess.check_output(
            ["curl", "-fsS", url],
            timeout=30,
            text=True,
        )
        return json.loads(raw)
    except Exception:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode())


def geocode_city(city: str) -> dict:
    name = city.strip()
    if not name:
        raise CityNotFound(city)
    query = urllib.parse.urlencode(
        {"name": name, "count": 1, "language": "en", "format": "json"}
    )
    data = _get_json(f"https://geocoding-api.open-meteo.com/v1/search?{query}")
    results = data.get("results") or []
    if not results:
        raise CityNotFound(name)
    return results[0]


def fetch_city_weather(city: str) -> WeatherReport:
    """Current temperature, humidity, US AQI, and wind speed for any city name."""
    place = geocode_city(city)
    lat = place["latitude"]
    lon = place["longitude"]
    timezone = place.get("timezone") or "UTC"
    tz = urllib.parse.quote(timezone)
    forecast = _get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
        f"&timezone={tz}"
    )
    air = _get_json(
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        "&current=us_aqi"
        f"&timezone={tz}"
    )
    current = forecast["current"]
    aqi = air.get("current", {}).get("us_aqi")
    if aqi is None:
        raise ValueError(f"Air quality unavailable for {place.get('name', city)}")
    return WeatherReport(
        city=place.get("name") or city.strip(),
        country=place.get("country") or "",
        latitude=float(lat),
        longitude=float(lon),
        timezone=timezone,
        observed_at=current["time"],
        temperature_c=float(current["temperature_2m"]),
        humidity_percent=int(current["relative_humidity_2m"]),
        aqi=int(aqi),
        wind_speed_kmh=float(current["wind_speed_10m"]),
    )


def fetch_temperature_c() -> tuple[float, datetime]:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={BANGALORE_LAT}&longitude={BANGALORE_LON}"
        "&current=temperature_2m&timezone=Asia%2FKolkata"
    )
    data = _get_json(url)
    temp = float(data["current"]["temperature_2m"])
    stamp = datetime.fromisoformat(data["current"]["time"]).replace(tzinfo=IST)
    return temp, stamp


def format_line(temp: float, stamp: datetime) -> str:
    return f"- {stamp.strftime('%Y-%m-%d %H:%M')} IST: {temp:.1f}°C"


def ensure_note() -> Note:
    for note in store.list_notes():
        if note.title == NOTE_TITLE:
            return note
    return store.create(
        NoteCreate(
            title=NOTE_TITLE,
            body=HEADER,
            tags=NOTE_TAGS,
        )
    )


def trim_body(body: str) -> str:
    if len(body) <= MAX_BODY:
        return body
    entries = [ln for ln in body.splitlines() if ln.startswith("- ")]
    kept: list[str] = []
    for line in reversed(entries):
        candidate = HEADER + "\n" + "\n".join([line, *kept])
        if len(candidate) > MAX_BODY:
            break
        kept.insert(0, line)
    return HEADER + ("\n" + "\n".join(kept) if kept else "")


def append_reading(note_id: str, line: str) -> str:
    note = store.get(note_id)
    if note is None:
        raise ValueError(f"Note not found: {note_id}")
    if line in note.body:
        return f"already logged: {line}"
    store.append(note_id, line)
    updated = store.get(note_id)
    if updated and len(updated.body) > MAX_BODY:
        store.update(note_id, NoteUpdate(body=trim_body(updated.body)))
    return f"appended: {line}"


def fetch_and_log_bangalore_temp() -> str:
    """Fetch current Bangalore temperature and append it to the note. Returns status text."""
    temp, stamp = fetch_temperature_c()
    line = format_line(temp, stamp)
    note = ensure_note()
    status = append_reading(note.id, line)
    return (
        f"{status}\n"
        f"note_id={note.id}\n"
        f"title={NOTE_TITLE}\n"
        f"temperature_c={temp:.1f}\n"
        f"time={stamp.strftime('%Y-%m-%d %H:%M')} IST"
    )
