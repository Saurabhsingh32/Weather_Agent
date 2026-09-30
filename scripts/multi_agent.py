#!/usr/bin/env python3
"""Coordinator agent that delegates to notes, weather, and summarizer subagents."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.executable).resolve() != _VENV_PYTHON.resolve():
    try:
        __import__("cursor_sdk")
    except ModuleNotFoundError:
        os.execv(
            str(_VENV_PYTHON),
            [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
        )

from cursor_sdk import (
    Agent,
    AgentDefinition,
    AgentOptions,
    CursorAgentError,
    CustomTool,
    CustomToolContext,
    LocalAgentOptions,
    StdioMcpServerConfig,
)

ROOT = _ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.weather import fetch_and_log_bangalore_temp, fetch_city_weather  # noqa: E402
from cursor_model import model_label, resolve_model  # noqa: E402

NOTES_PROMPT = """You are the notes specialist.

Use the notes MCP tools only. Do not invent note ids.

Workflow:
1. Call list_notes or search_notes before get_note, update_note, append_note, or delete_note.
2. Prefer append_note when adding lines to an existing list (grocery items, bullets).
3. Create with create_note when no matching note exists.
4. Report title, status, tags, and the relevant body snippet when done.

Never invent weather readings; that is the weather agent's job.
"""

WEATHER_PROMPT = """You are the weather specialist for any city.

When the user asks for the weather of a city, call get_city_weather with that city name.
Report temperature_c, humidity_percent, aqi (US AQI), and wind_speed_kmh from the tool.
Never invent or estimate readings.

When the user asks to log Bangalore temperature into the note, call log_bangalore_temperature
instead, then report the temperature, timestamp (IST), and whether the line was appended
or already logged.
"""

SUMMARIZER_PROMPT = """You are the summarizer specialist.

Read notes with list_notes, search_notes, get_note, and list_tags only.
Never create, update, append, or delete notes.

Produce a short plain-language briefing. Include grocery and Current temperature highlights
when those notes exist. If something is missing, say so.
"""

DEFAULT_PROMPT = (
    "You are the coordinator. Delegate with the Agent tool:\n"
    "- notes — grocery lists and any note create/search/update/append/delete\n"
    "- weather — current weather for any city (temperature, humidity, AQI, wind)\n"
    "- summarizer — read-only briefings from notes\n"
    "You may use multiple subagents for multi-part requests, then combine their results.\n\n"
    "Task: Log Bangalore temperature via the weather subagent. "
    "Via the notes subagent, if a Grocery note exists append '- Eggs', otherwise create "
    "Grocery with milk and eggs tagged errand. "
    "Then use the summarizer subagent for a short briefing of grocery + temperature. "
    "Finally reply with the combined results."
)


def _log_bangalore_temperature(args: dict, context: CustomToolContext) -> str:
    del args, context
    return fetch_and_log_bangalore_temp()


def _get_city_weather(args: dict, context: CustomToolContext) -> str:
    del context
    report = fetch_city_weather(str(args["city"]))
    return report.model_dump_json()


def main() -> int:
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        print(
            "CURSOR_API_KEY is required. Create one at "
            "https://cursor.com/dashboard/integrations",
            file=sys.stderr,
        )
        return 1

    prompt = " ".join(sys.argv[1:]).strip() or DEFAULT_PROMPT
    venv_python = ROOT / ".venv" / "bin" / "python"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable
    model = resolve_model(api_key)
    print(f"using model: {model_label(model)}", flush=True)

    try:
        with Agent.create(
            AgentOptions(
                api_key=api_key,
                model=model,
                name="notes-multi-agent",
                local=LocalAgentOptions(
                    cwd=str(ROOT),
                    custom_tools={
                        "get_city_weather": CustomTool(
                            description=(
                                "Fetch current weather for any city: temperature °C, "
                                "humidity %, US AQI, and wind speed km/h."
                            ),
                            input_schema={
                                "type": "object",
                                "properties": {
                                    "city": {
                                        "type": "string",
                                        "description": "City name, for example Lucknow or Bengaluru",
                                    }
                                },
                                "required": ["city"],
                                "additionalProperties": False,
                            },
                            execute=_get_city_weather,
                        ),
                        "log_bangalore_temperature": CustomTool(
                            description=(
                                "Fetch Bangalore's current temperature from Open-Meteo "
                                "and append it to the Current temperature note in SQLite."
                            ),
                            input_schema={
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                            execute=_log_bangalore_temperature,
                        ),
                    },
                ),
                mcp_servers={
                    "notes": StdioMcpServerConfig(
                        command=python_cmd,
                        args=["-m", "app.mcp_server"],
                        cwd=str(ROOT),
                    ),
                },
                agents={
                    "notes": AgentDefinition(
                        description=(
                            "Manage notes via the notes MCP — grocery lists, "
                            "create/search/update/append/delete."
                        ),
                        prompt=NOTES_PROMPT,
                        model="inherit",
                        mcp_servers=["notes"],
                    ),
                    "weather": AgentDefinition(
                        description=(
                            "Current weather for any city: temperature, humidity, "
                            "US AQI, and wind speed. Also logs Bangalore temperature "
                            "when asked."
                        ),
                        prompt=WEATHER_PROMPT,
                        model="inherit",
                    ),
                    "summarizer": AgentDefinition(
                        description=(
                            "Read-only briefing from notes (grocery, temperature, tags)."
                        ),
                        prompt=SUMMARIZER_PROMPT,
                        model="inherit",
                        mcp_servers=["notes"],
                    ),
                },
            )
        ) as agent:
            run = agent.send(prompt)
            saw_text = False
            for message in run.messages():
                msg_type = getattr(message, "type", None)
                if msg_type == "assistant":
                    content = getattr(getattr(message, "message", None), "content", None)
                    if content is None:
                        continue
                    for block in content:
                        if getattr(block, "type", None) == "text":
                            saw_text = True
                            print(block.text, end="", flush=True)
                elif msg_type in {"status", "error", "tool_call", "thinking"}:
                    # Extra visibility when the assistant prints nothing.
                    detail = getattr(message, "status", None) or getattr(
                        message, "text", None
                    )
                    print(f"\n[{msg_type}] {detail or message}", file=sys.stderr)
            if saw_text:
                print()
            result = run.wait()
            if result.status == "error":
                print(f"run failed: {result.id}", file=sys.stderr)
                if result.result:
                    print(f"result: {result.result}", file=sys.stderr)
                if run.supports("conversation"):
                    try:
                        conversation = run.conversation()
                        print(f"conversation: {conversation!r}", file=sys.stderr)
                    except Exception as conv_err:  # noqa: BLE001
                        print(f"conversation unavailable: {conv_err}", file=sys.stderr)
                print(
                    "Hint: try a simpler check first:\n"
                    '  python scripts/notes_agent.py "List notes with the notes MCP"\n'
                    "If that also fails, recreate the API key at "
                    "https://cursor.com/dashboard/integrations",
                    file=sys.stderr,
                )
                return 2
    except CursorAgentError as err:
        print(
            f"startup failed: {err.message}, retryable={err.is_retryable}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
