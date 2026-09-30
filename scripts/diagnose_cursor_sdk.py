#!/usr/bin/env python3
"""Minimal Cursor SDK diagnosis: auth, models, and a no-MCP prompt."""

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

from cursor_sdk import Agent, AgentOptions, Cursor, CursorAgentError, LocalAgentOptions

sys.path.insert(0, str(_ROOT / "scripts"))
from cursor_model import model_label, resolve_model  # noqa: E402


def main() -> int:
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        print("CURSOR_API_KEY is not set", file=sys.stderr)
        return 1

    prefix = api_key.split("_", 1)[0] + "_" if "_" in api_key else "(no underscore)"
    print(f"key length: {len(api_key)}")
    print(f"key prefix: {prefix}")
    if not api_key.startswith(("cursor_", "crsr_")):
        print(
            "WARN: unexpected key prefix. User API keys usually start with "
            "cursor_ or crsr_. Create one at https://cursor.com/dashboard/integrations",
            file=sys.stderr,
        )

    print("\n== Catalog details ==")
    try:
        models = Cursor.models.list(api_key=api_key)
        for item in models:
            variants = []
            for v in item.variants:
                params = ",".join(f"{p.id}={p.value}" for p in v.params)
                mark = " (default)" if v.is_default else ""
                variants.append(f"{v.display_name or params or 'variant'}{mark}")
            print(f"- {item.id}: variants={variants or ['(none)']}")
    except Exception as err:  # noqa: BLE001
        print(f"models.list FAILED: {type(err).__name__}: {err}", file=sys.stderr)
        return 1

    print("\n== Agent.create + stream events (no MCP) ==")
    model = resolve_model(api_key)
    print(f"resolved model: {model_label(model)}")
    try:
        with Agent.create(
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=str(_ROOT)),
            )
        ) as agent:
            run = agent.send("Reply with exactly: SDK_OK")
            print(f"run_id: {run.id}")
            for event in run.events():
                sdk = getattr(event, "sdk_message", None)
                if sdk is None:
                    print(f"event: {event!r}")
                    continue
                msg_type = getattr(sdk, "type", type(sdk).__name__)
                if msg_type == "assistant":
                    texts = []
                    content = getattr(getattr(sdk, "message", None), "content", ())
                    for block in content:
                        if getattr(block, "type", None) == "text":
                            texts.append(block.text)
                    print(f"assistant: {''.join(texts)!r}")
                elif msg_type == "status":
                    print(
                        f"status: {getattr(sdk, 'status', None)} "
                        f"message={getattr(sdk, 'message', None)!r} "
                        f"text={getattr(sdk, 'text', None)!r}"
                    )
                else:
                    print(f"{msg_type}: {sdk!r}")
            result = run.wait()
            print(f"wait status: {result.status}")
            print(f"wait result: {result.result!r}")
            print(f"duration_ms: {result.duration_ms}")
            if result.status == "error":
                print(
                    "\nRun failed. Common causes on Start:\n"
                    "  - Bare model id without fixed settings (scripts now send catalog default)\n"
                    "  - Usage limit → try: export CURSOR_MODEL=auto\n"
                    "  - Plan restriction → upgrade or wait for quota reset\n"
                    "Override examples:\n"
                    "  export CURSOR_MODEL=auto\n"
                    "  export CURSOR_MODEL=composer-2.5:fast=true\n"
                    "  export CURSOR_MODEL=grok-4.6",
                    file=sys.stderr,
                )
                return 2
    except CursorAgentError as err:
        print(
            f"startup failed: {err.message}, retryable={err.is_retryable}",
            file=sys.stderr,
        )
        return 1
    except Exception as err:  # noqa: BLE001
        print(f"prompt FAILED: {type(err).__name__}: {err}", file=sys.stderr)
        return 1

    print("\nPASS: basic SDK auth + prompt works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
