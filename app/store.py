import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models import Note, NoteCreate, NoteStatus, NoteUpdate, TagCount


def _default_db_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "notes.db"


class NoteStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        raw = db_path if db_path is not None else os.environ.get("NOTES_DB_PATH")
        self._db_path = Path(raw) if raw else _default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        if self.count() == 0:
            self._seed()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _seed(self) -> None:
        samples = [
            NoteCreate(
                title="MCP wrapping plan",
                body="Expose list, get, create, update, delete, and search as MCP tools.",
                tags=["mcp", "plan"],
            ),
            NoteCreate(
                title="FastAPI notes",
                body="Keep request/response models explicit so tool schemas stay stable.",
                tags=["fastapi", "design"],
            ),
            NoteCreate(
                title="Archived idea",
                body="A discarded sketch for a chat-only interface.",
                tags=["archive"],
                status=NoteStatus.archived,
            ),
        ]
        for sample in samples:
            self.create(sample)

    def _row_to_note(self, row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            tags=json.loads(row["tags"]),
            status=NoteStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_notes(self, status: NoteStatus | None = None) -> list[Note]:
        with self._connect() as conn:
            if status is not None:
                rows = conn.execute(
                    """
                    SELECT * FROM notes
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    """,
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notes ORDER BY updated_at DESC"
                ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def get(self, note_id: str) -> Note | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ?",
                (note_id,),
            ).fetchone()
        return self._row_to_note(row) if row else None

    def create(self, payload: NoteCreate) -> Note:
        now = self._now()
        note = Note(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notes (id, title, body, tags, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.id,
                    note.title,
                    note.body,
                    json.dumps(note.tags),
                    note.status.value,
                    note.created_at.isoformat(),
                    note.updated_at.isoformat(),
                ),
            )
            conn.commit()
        return note

    def update(self, note_id: str, payload: NoteUpdate) -> Note | None:
        existing = self.get(note_id)
        if existing is None:
            return None
        data = existing.model_dump()
        data.update(payload.model_dump(exclude_unset=True))
        data["updated_at"] = self._now()
        note = Note(**data)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, body = ?, tags = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    note.title,
                    note.body,
                    json.dumps(note.tags),
                    note.status.value,
                    note.updated_at.isoformat(),
                    note.id,
                ),
            )
            conn.commit()
        return note

    def append(self, note_id: str, text: str) -> Note | None:
        existing = self.get(note_id)
        if existing is None:
            return None
        chunk = text.lstrip("\n")
        if not chunk:
            return existing
        if existing.body and not existing.body.endswith("\n"):
            new_body = f"{existing.body}\n{chunk}"
        else:
            new_body = f"{existing.body}{chunk}"
        return self.update(note_id, NoteUpdate(body=new_body))

    def delete(self, note_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
            return cursor.rowcount > 0

    def search(
        self,
        query: str,
        status: NoteStatus | None = None,
        tag: str | None = None,
    ) -> list[Note]:
        needle = query.lower()
        results: list[Note] = []
        for note in self.list_notes(status=status):
            if tag and tag not in note.tags:
                continue
            haystack = f"{note.title} {note.body} {' '.join(note.tags)}".lower()
            if needle in haystack:
                results.append(note)
        return results

    def list_tags(self) -> list[TagCount]:
        counts: dict[str, int] = {}
        for note in self.list_notes():
            for tag in note.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return [
            TagCount(tag=tag, count=count)
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM notes").fetchone()
        return int(row["n"]) if row else 0


store = NoteStore()
