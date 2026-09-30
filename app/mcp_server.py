from typing import Optional

from fastmcp import FastMCP

from app.models import (
    HealthResponse,
    Note,
    NoteAppendRequest,
    NoteCreate,
    NoteDeleteResponse,
    NoteListResponse,
    NoteSearchRequest,
    NoteSearchResponse,
    NoteStatus,
    NoteUpdate,
    TagListResponse,
    WeatherReport,
)
from app import services

mcp = FastMCP(
    name="Notes MCP",
    instructions=(
        "Notes tools that match the HTTP API. Use list_notes or search_notes "
        "before get_note, update_note, append_note, or delete_note so you have "
        "a valid id. Prefer append_note when adding lines to an existing list. "
        "Use get_weather when the user asks for the weather of a city."
    ),
)


@mcp.tool
def get_weather(city: str) -> WeatherReport:
    """Current weather for a city: temperature °C, humidity %, US AQI, and wind speed km/h."""
    return services.city_weather(city)


@mcp.tool
def health() -> HealthResponse:
    """Check that the notes service is running and how many notes it holds."""
    return services.health()


@mcp.tool
def list_notes(status: Optional[NoteStatus] = None) -> NoteListResponse:
    """List notes, optionally filtered by status (draft, active, archived)."""
    return services.list_notes(status=status)


@mcp.tool
def list_tags() -> TagListResponse:
    """List distinct tags with how many notes use each tag."""
    return services.list_tags()


@mcp.tool
def get_note(note_id: str) -> Note:
    """Fetch one note by id."""
    return services.get_note(note_id)


@mcp.tool
def create_note(payload: NoteCreate) -> Note:
    """Create a note. Status defaults to active."""
    return services.create_note(payload)


@mcp.tool
def update_note(note_id: str, payload: NoteUpdate) -> Note:
    """Update fields on an existing note. Omit fields you do not want to change."""
    return services.update_note(note_id, payload)


@mcp.tool
def append_note(note_id: str, payload: NoteAppendRequest) -> Note:
    """Append text to a note body (e.g. grocery lines). Prefer over full body replace."""
    return services.append_note(note_id, payload)


@mcp.tool
def delete_note(note_id: str) -> NoteDeleteResponse:
    """Delete a note by id."""
    return services.delete_note(note_id)


@mcp.tool
def search_notes(payload: NoteSearchRequest) -> NoteSearchResponse:
    """Search notes by text in title, body, or tags. Optional status and tag filters."""
    return services.search_notes(payload)


if __name__ == "__main__":
    mcp.run()
