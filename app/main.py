from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from app.mcp_server import mcp
from app.models import (
    HealthResponse,
    Note,
    NoteAppendRequest,
    NoteCreate,
    NoteListResponse,
    NoteSearchRequest,
    NoteSearchResponse,
    NoteStatus,
    NoteUpdate,
    TagListResponse,
    WeatherReport,
)
from app import services
from app.services import NoteNotFound
from app.weather import CityNotFound

mcp_http = mcp.http_app(path="/")

app = FastAPI(
    title="Notes API",
    description=(
        "HTTP notes API plus MCP at /mcp. Route handlers and MCP tools share "
        "app.models and app.services. Notes persist in SQLite (NOTES_DB_PATH)."
    ),
    version="0.1.0",
    lifespan=mcp_http.lifespan,
)
app.mount("/mcp", mcp_http)


def _not_found(exc: NoteNotFound) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return services.health()


@app.get("/weather", response_model=WeatherReport)
def weather(city: str = Query(..., min_length=1, max_length=200)) -> WeatherReport:
    try:
        return services.city_weather(city)
    except CityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/notes", response_model=NoteListResponse)
def list_notes(
    status: Optional[NoteStatus] = Query(default=None),
) -> NoteListResponse:
    return services.list_notes(status=status)


@app.get("/notes/tags", response_model=TagListResponse)
def list_tags() -> TagListResponse:
    return services.list_tags()


@app.get("/notes/{note_id}", response_model=Note)
def get_note(note_id: str) -> Note:
    try:
        return services.get_note(note_id)
    except NoteNotFound as exc:
        raise _not_found(exc) from exc


@app.post("/notes", response_model=Note, status_code=201)
def create_note(payload: NoteCreate) -> Note:
    return services.create_note(payload)


@app.patch("/notes/{note_id}", response_model=Note)
def update_note(note_id: str, payload: NoteUpdate) -> Note:
    try:
        return services.update_note(note_id, payload)
    except NoteNotFound as exc:
        raise _not_found(exc) from exc


@app.post("/notes/{note_id}/append", response_model=Note)
def append_note(note_id: str, payload: NoteAppendRequest) -> Note:
    try:
        return services.append_note(note_id, payload)
    except NoteNotFound as exc:
        raise _not_found(exc) from exc


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: str) -> None:
    try:
        services.delete_note(note_id)
    except NoteNotFound as exc:
        raise _not_found(exc) from exc


@app.post("/notes/search", response_model=NoteSearchResponse)
def search_notes(payload: NoteSearchRequest) -> NoteSearchResponse:
    return services.search_notes(payload)
