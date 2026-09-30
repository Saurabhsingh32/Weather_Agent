from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NoteStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Short note title")
    body: str = Field(..., min_length=1, max_length=8000, description="Full note text")
    tags: list[str] = Field(default_factory=list, description="Optional labels")
    status: NoteStatus = Field(default=NoteStatus.active, description="draft, active, or archived")


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, min_length=1, max_length=8000)
    tags: Optional[list[str]] = None
    status: Optional[NoteStatus] = None


class Note(NoteCreate):
    id: str = Field(..., description="Note identifier")
    created_at: datetime
    updated_at: datetime


class NoteSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="Text to find in title, body, or tags")
    status: Optional[NoteStatus] = Field(default=None, description="Optional status filter")
    tag: Optional[str] = Field(default=None, description="Optional exact tag filter")


class NoteListResponse(BaseModel):
    items: list[Note]
    count: int


class NoteSearchResponse(BaseModel):
    items: list[Note]
    count: int
    query: str


class HealthResponse(BaseModel):
    status: str
    service: str
    note_count: int


class WeatherReport(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    observed_at: str
    temperature_c: float
    humidity_percent: int
    aqi: int
    aqi_scale: str = "US AQI"
    wind_speed_kmh: float


class NoteDeleteResponse(BaseModel):
    deleted: bool
    id: str


class NoteAppendRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Text to append to the note body (e.g. grocery lines)",
    )


class TagCount(BaseModel):
    tag: str
    count: int


class TagListResponse(BaseModel):
    items: list[TagCount]
    count: int
