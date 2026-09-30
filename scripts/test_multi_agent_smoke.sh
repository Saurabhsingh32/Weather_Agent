#!/usr/bin/env bash
# Smoke test for scripts/multi_agent.py (coordinator + notes / weather / summarizer).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PREFLIGHT_ONLY=0
if [[ "${1:-}" == "--preflight-only" ]]; then
  PREFLIGHT_ONLY=1
fi

VENV_PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${VENV_PY}" ]]; then
  echo "FAIL: missing venv at ${ROOT}/.venv (run: python3 -m venv .venv && pip install -r requirements.txt)" >&2
  exit 1
fi

echo "== Preflight =="
"${VENV_PY}" -c "
import importlib
import sys
from pathlib import Path

root = Path('${ROOT}')
sys.path.insert(0, str(root))

importlib.import_module('cursor_sdk')
importlib.import_module('app.mcp_server')
importlib.import_module('app.weather')
from app.weather import fetch_city_weather

report = fetch_city_weather('Bengaluru')
assert report.temperature_c is not None
print('cursor-sdk: ok')
print('notes MCP module: ok')
print(f'weather tool: ok (Bengaluru {report.temperature_c}°C)')
"

DB_PATH="${NOTES_DB_PATH:-${ROOT}/data/notes.db}"
export DB_PATH
echo "notes DB: ${DB_PATH}"

"${VENV_PY}" - <<'PY'
import json
import os
import sqlite3
from pathlib import Path

db = Path(os.environ["DB_PATH"])
if not db.exists():
    print(f"WARN: {db} does not exist yet (will be created on first note write)")
else:
    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    con.close()
    print(f"notes row count: {n}")
PY

if [[ "${PREFLIGHT_ONLY}" -eq 1 ]]; then
  echo "PASS: preflight only (--preflight-only)"
  exit 0
fi

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
  echo "SKIP: integration test (export CURSOR_API_KEY from https://cursor.com/dashboard/integrations)" >&2
  echo "PASS: preflight; run again with CURSOR_API_KEY set for full multi-agent smoke" >&2
  exit 2
fi

echo ""
echo "== Multi-agent integration (default coordinator task) =="
SNAPSHOT_BEFORE="${ROOT}/data/.multi_agent_smoke_before.json"
SNAPSHOT_AFTER="${ROOT}/data/.multi_agent_smoke_after.json"
export SNAPSHOT_BEFORE SNAPSHOT_AFTER

"${VENV_PY}" - <<'PY'
import json
import os
import sqlite3
from pathlib import Path

db = Path(os.environ["DB_PATH"])
out = Path(os.environ["SNAPSHOT_BEFORE"])
titles = ("Grocery", "Current temperature")
rows = {}
if db.exists():
    con = sqlite3.connect(db)
    for title in titles:
        row = con.execute(
            "SELECT id, title, body, updated_at FROM notes WHERE title = ?",
            (title,),
        ).fetchone()
        if row:
            rows[title] = {
                "id": row[0],
                "title": row[1],
                "body": row[2],
                "updated_at": row[3],
            }
    con.close()
out.write_text(json.dumps(rows, indent=2))
print(f"snapshot before: {out}")
PY

export SNAPSHOT_BEFORE
set +e
"${VENV_PY}" "${ROOT}/scripts/multi_agent.py" 2>&1 | tee "${ROOT}/data/.multi_agent_smoke.log"
AGENT_EXIT=${PIPESTATUS[0]}
set -e

if [[ "${AGENT_EXIT}" -ne 0 ]]; then
  echo "FAIL: multi_agent.py exited ${AGENT_EXIT}" >&2
  exit "${AGENT_EXIT}"
fi

export SNAPSHOT_AFTER
"${VENV_PY}" - <<'PY'
import json
import os
import sqlite3
import sys
from pathlib import Path

db = Path(os.environ["DB_PATH"])
before = json.loads(Path(os.environ["SNAPSHOT_BEFORE"]).read_text())
after_path = Path(os.environ["SNAPSHOT_AFTER"])
titles = ("Grocery", "Current temperature")
after = {}
if db.exists():
    con = sqlite3.connect(db)
    for title in titles:
        row = con.execute(
            "SELECT id, title, body, updated_at FROM notes WHERE title = ?",
            (title,),
        ).fetchone()
        if row:
            after[title] = {
                "id": row[0],
                "title": row[1],
                "body": row[2],
                "updated_at": row[3],
            }
    con.close()
after_path.write_text(json.dumps(after, indent=2))
print(f"snapshot after: {after_path}")

errors = []
grocery = after.get("Grocery")
if not grocery:
    errors.append("expected a Grocery note after default task")
elif "egg" not in grocery["body"].lower():
    errors.append("Grocery body should mention eggs (append or create)")

temp = after.get("Current temperature")
if not temp:
    errors.append("expected Current temperature note after weather subagent")
elif "IST:" not in temp["body"]:
    errors.append("Current temperature should contain IST log lines")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("DB assertions: ok (Grocery + Current temperature)")
PY

echo ""
echo "PASS: multi-agent smoke test"
echo "Log: ${ROOT}/data/.multi_agent_smoke.log"
