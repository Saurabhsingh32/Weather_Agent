# Notes API + MCP

HTTP notes API and matching MCP tools. Pydantic models in `app/models.py` are the schema. `app/services.py` is the shared logic. FastAPI routes and MCP tools call the same functions with the same fields.

Notes persist in **SQLite** (default `data/notes.db`). Set `NOTES_DB_PATH` to override. Three sample notes load only when the database is empty. HTTP and stdio MCP share storage when they use the same path.

## Endpoints and tools

| HTTP | Path | MCP tool |
|------|------|----------|
| `GET` | `/health` | `health` |
| `GET` | `/weather?city=` | `get_weather` |
| `GET` | `/notes` | `list_notes` |
| `GET` | `/notes/tags` | `list_tags` |
| `GET` | `/notes/{note_id}` | `get_note` |
| `POST` | `/notes` | `create_note` |
| `PATCH` | `/notes/{note_id}` | `update_note` |
| `POST` | `/notes/{note_id}/append` | `append_note` |
| `DELETE` | `/notes/{note_id}` | `delete_note` |
| `POST` | `/notes/search` | `search_notes` |

## Run the HTTP API (MCP at `/mcp`)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- REST docs: http://127.0.0.1:8000/docs
- MCP Streamable HTTP: http://127.0.0.1:8000/mcp

## Expose tools to Cursor (stdio)

Project config lives in `.cursor/mcp.json`. Use the venv Python so `fastmcp` is available:

```json
{
  "mcpServers": {
    "notes": {
      "command": "/Users/saurabh/learning_projects/agentic_web_app/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Users/saurabh/learning_projects/agentic_web_app"
    }
  }
}
```

Then reload MCP / restart Cursor. The agent should see `health`, `list_notes`, `list_tags`, `get_note`, `create_note`, `update_note`, `append_note`, `delete_note`, and `search_notes`.

You can also point an HTTP MCP client at `http://127.0.0.1:8000/mcp` after uvicorn is running.

## Agent skill

Project skill: `.cursor/skills/notes/SKILL.md`.

Cursor loads that file when you work in this repo and talk about notes. It tells the agent to use the **notes** MCP tools (list/search first, then get/update/append/delete by id) instead of guessing ids or hitting REST unless you ask.

Skills are instructions, not extra endpoints. MCP still does the actual create/list/search work.

## Cursor SDK local agent

`scripts/notes_agent.py` runs a **local** Cursor agent that uses the notes MCP over stdio (same entrypoint as `.cursor/mcp.json`).

1. Get an API key from [Cursor Dashboard → Integrations](https://cursor.com/dashboard/integrations).
2. Install deps (includes `cursor-sdk`).
3. Run:

```bash
export CURSOR_API_KEY="cursor_..."
source .venv/bin/activate
python scripts/notes_agent.py
# or with a custom prompt:
python scripts/notes_agent.py "Search for grocery and append butter and yogurt"
```

The script fails fast if `CURSOR_API_KEY` is missing. It passes MCP servers inline only (does not load ambient Cursor settings).

## Multi-agent (coordinator + subagents)

`scripts/multi_agent.py` runs a **coordinator** local agent that delegates via the Agent tool to three specialists:

| Subagent | Role |
|----------|------|
| `notes` | Notes MCP — create/search/update/append/delete (grocery lists, etc.) |
| `weather` | `get_city_weather` for any city (temperature, humidity, US AQI, wind). `log_bangalore_temperature` still writes the Current temperature note |
| `summarizer` | Read-only briefing from notes (no mutations) |

File-based defs for Cursor IDE: `.cursor/agents/notes.md`, `weather.md`, `summarizer.md`. The SDK script passes the same roles **inline** (does not load ambient settings).

```bash
export CURSOR_API_KEY="cursor_..."
source .venv/bin/activate
python scripts/multi_agent.py
# or:
python scripts/multi_agent.py "Log Bangalore temp, add eggs to grocery if present, then summarize"
```

Keep `scripts/notes_agent.py` for simple single-agent notes tasks. Use `multi_agent.py` when the request spans notes + weather + summary.

Smoke test (preflight without API key; full run with `CURSOR_API_KEY`):

```bash
chmod +x scripts/test_multi_agent_smoke.sh
./scripts/test_multi_agent_smoke.sh --preflight-only
export CURSOR_API_KEY="cursor_..."
./scripts/test_multi_agent_smoke.sh
```

Reload the **notes** MCP in Cursor so IDE chat and the weather logger share SQLite (`data/notes.db`).

## Weather for any city

`GET /weather?city=Lucknow` and the MCP tool `get_weather` resolve the city with Open-Meteo geocoding, then return current temperature (°C), humidity (%), US AQI, and wind speed (km/h). No API key.

```bash
curl "http://127.0.0.1:8000/weather?city=Lucknow"
```

In Cursor, a prompt such as "give me the weather details of Lucknow" should call `get_weather`. Reload the **notes** MCP after this change so the new tool is visible.

## Bangalore temperature logger

`scripts/log_bangalore_temp.py` (logic in `app/weather.py`) creates/updates a note titled **Current temperature** with Bangalore readings from [Open-Meteo](https://open-meteo.com/) (no API key).

```bash
source .venv/bin/activate
python scripts/log_bangalore_temp.py
```

Hourly cron (already installable):

```cron
0 * * * * /Users/saurabh/learning_projects/agentic_web_app/.venv/bin/python /Users/saurabh/learning_projects/agentic_web_app/scripts/log_bangalore_temp.py >> /Users/saurabh/learning_projects/agentic_web_app/data/bangalore_temp.log 2>> /Users/saurabh/learning_projects/agentic_web_app/data/bangalore_temp.err
```

Reload the **notes** MCP in Cursor so it uses the shared SQLite DB (`data/notes.db`) and can see this note.

## Kubernetes (Docker Desktop, 3 replicas)

This repo targets **Docker Desktop Kubernetes**. Confirm the cluster:

```bash
kubectl config current-context   # expect: docker-desktop
kubectl get nodes
```

If Kubernetes is off: Docker Desktop → Settings → Kubernetes → Enable Kubernetes.

### Build and deploy (recommended)

Docker Desktop often cannot use local-only images (`ErrImageNeverPull`). The deploy script builds, pushes to the ephemeral registry [ttl.sh](https://ttl.sh), and applies manifests with **3 replicas**:

```bash
cd /Users/saurabh/learning_projects/agentic_web_app
./scripts/k8s-deploy.sh
kubectl -n agentic-web-app get pods,svc
```

Service type is `LoadBalancer` on port **8000**.

```bash
curl http://127.0.0.1:8000/health
open http://127.0.0.1:8000/docs
```

### Manual apply

```bash
docker build -t agentic-web-app:latest .
docker tag agentic-web-app:latest ttl.sh/agentic-web-app-$USER:2h
docker push ttl.sh/agentic-web-app-$USER:2h
# set image in k8s/10-deployment.yaml to that tag, then:
kubectl apply -f k8s/
```

### Notes on storage

Each pod uses its own ephemeral SQLite (`emptyDir`). With 3 replicas, requests can hit different pods, so note data is **not shared** across replicas. That is intentional for a safe local scale-out demo; use a real database (e.g. Postgres) if you need shared persistence.

### Tear down

```bash
kubectl delete -f k8s/
```
