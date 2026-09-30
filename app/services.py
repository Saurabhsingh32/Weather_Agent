from typing import Optional

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
from app.store import store
from app.weather import fetch_city_weather


class NoteNotFound(Exception):
    def __init__(self, note_id: str) -> None:
        super().__init__(f"Note not found: {note_id}")
        self.note_id = note_id


def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="notes-api",
        note_count=store.count(),
    )


def city_weather(city: str) -> WeatherReport:
    return fetch_city_weather(city)


def list_notes(status: Optional[NoteStatus] = None) -> NoteListResponse:
    items = store.list_notes(status=status)
    return NoteListResponse(items=items, count=len(items))


def get_note(note_id: str) -> Note:
    note = store.get(note_id)
    if note is None:
        raise NoteNotFound(note_id)
    return note


def create_note(payload: NoteCreate) -> Note:
    return store.create(payload)


def update_note(note_id: str, payload: NoteUpdate) -> Note:
    note = store.update(note_id, payload)
    if note is None:
        raise NoteNotFound(note_id)
    return note


def append_note(note_id: str, payload: NoteAppendRequest) -> Note:
    note = store.append(note_id, payload.text)
    if note is None:
        raise NoteNotFound(note_id)
    return note


def delete_note(note_id: str) -> NoteDeleteResponse:
    if not store.delete(note_id):
        raise NoteNotFound(note_id)
    return NoteDeleteResponse(deleted=True, id=note_id)


def search_notes(payload: NoteSearchRequest) -> NoteSearchResponse:
    items = store.search(query=payload.query, status=payload.status, tag=payload.tag)
    return NoteSearchResponse(items=items, count=len(items), query=payload.query)


def list_tags() -> TagListResponse:
    items = store.list_tags()
    return TagListResponse(items=items, count=len(items))
