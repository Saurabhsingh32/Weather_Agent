#!/usr/bin/env python3
"""Run a local Cursor agent that manages notes via the project MCP server."""

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

from cursor_sdk import Agent, AgentOptions, LocalAgentOptions, StdioMcpServerConfig
from cursor_sdk import CursorAgentError

ROOT = _ROOT
sys.path.insert(0, str(ROOT / "scripts"))
from cursor_model import model_label, resolve_model  # noqa: E402

DEFAULT_PROMPT = (
    "Use the notes MCP tools. Search or list notes for 'grocery'. "
    "If a Grocery note exists, append these lines with append_note: "
    "- Butter\n- Yogurt. "
    "If it does not exist, create one titled Grocery with milk, eggs, butter, and yogurt, "
    "tagged errand. Then summarize the final grocery body."
)


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
                local=LocalAgentOptions(cwd=str(ROOT)),
                mcp_servers={
                    "notes": StdioMcpServerConfig(
                        command=python_cmd,
                        args=["-m", "app.mcp_server"],
                        cwd=str(ROOT),
                    ),
                },
            )
        ) as agent:
            run = agent.send(prompt)
            for message in run.messages():
                msg_type = getattr(message, "type", None)
                if msg_type == "assistant":
                    content = getattr(getattr(message, "message", None), "content", None)
                    if content is None:
                        continue
                    for block in content:
                        if getattr(block, "type", None) == "text":
                            print(block.text, end="", flush=True)
                elif msg_type in {"status", "error"}:
                    detail = getattr(message, "status", None) or getattr(
                        message, "text", None
                    )
                    print(f"\n[{msg_type}] {detail or message}", file=sys.stderr)
            print()
            result = run.wait()
            if result.status == "error":
                print(f"run failed: {result.id}", file=sys.stderr)
                if result.result:
                    print(f"result: {result.result}", file=sys.stderr)
                if run.supports("conversation"):
                    try:
                        print(f"conversation: {run.conversation()!r}", file=sys.stderr)
                    except Exception as conv_err:  # noqa: BLE001
                        print(f"conversation unavailable: {conv_err}", file=sys.stderr)
                print(
                    "Next: run scripts/diagnose_cursor_sdk.py to test auth without MCP.\n"
                    "API keys from https://cursor.com/dashboard/integrations usually "
                    "start with cursor_",
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
