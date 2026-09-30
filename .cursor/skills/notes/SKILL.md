---
name: notes
description: Manage notes through the project Notes MCP tools (list, search, get, create, update, append, delete, tags, health). Use when the user mentions notes, grocery lists, tags, draft/active/archived status, or asks to read or change note content in this workspace.
---

# Notes

Use the **notes** MCP server in this project. Do not call the HTTP API unless the user asks for REST/`curl`/`/docs`.

## Tool workflow

1. Inspect tool schemas before the first call.
2. **list_notes** or **search_notes** before **get_note**, **update_note**, **append_note**, or **delete_note**. Never invent an id.
3. Create with **create_note** and `payload`: `title`, `body`, optional `tags`, optional `status` (`draft` | `active` | `archived`). Default status is `active`.
4. Update with **update_note**: pass only fields that should change.
5. Prefer **append_note** when adding lines to an existing list (grocery items, bullets) instead of replacing the whole body.
6. Summarize results in plain language. Include title, status, tags, and body when the user asked to see content.

## Mapping

| User intent | Tool |
|-------------|------|
| Are notes working? How many? | `health` |
| Show all / filter by status | `list_notes` |
| Show tags and counts | `list_tags` |
| Find by text or tag | `search_notes` |
| Show one note | `get_note` |
| New note | `create_note` |
| Edit title, body, tags, status | `update_note` |
| Add lines to body | `append_note` |
| Remove | `delete_note` |

## Constraints

- Storage is SQLite. Default path is `data/notes.db`; override with `NOTES_DB_PATH`.
- HTTP (uvicorn) and stdio MCP share the same DB file when they use the same `NOTES_DB_PATH`, so edits survive process restarts.
- Seed notes load only when the database is empty.
- If tools are missing, tell the user to enable the **notes** MCP server in Cursor Settings → MCP.
