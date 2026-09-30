#!/usr/bin/env python3
"""CLI: fetch Bangalore temperature and append it to the Current temperature note."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.weather import fetch_and_log_bangalore_temp  # noqa: E402


def main() -> int:
    print(fetch_and_log_bangalore_temp())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
