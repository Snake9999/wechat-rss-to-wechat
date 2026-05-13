#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def main() -> int:
    if len(sys.argv) <= 1:
        print(
            "Usage: python skill/scripts/run_pipeline.py [prepare|bootstrap|doctor|sync|candidates|run] [args...]",
            file=sys.stderr,
        )
        return 1

    action = sys.argv[1]
    extra_args = sys.argv[2:] if len(sys.argv) > 2 else []

    action_map = {
        "prepare": "prepare",
        "bootstrap": "bootstrap",
        "doctor": "doctor",
        "sync": "sync-sources",
        "candidates": "daily-candidates",
        "run": "run-once",
    }

    command_name = action_map.get(action)
    if command_name is None:
        print(f"[FAIL] unknown action: {action}", file=sys.stderr)
        print(
            "Usage: python skill/scripts/run_pipeline.py [prepare|bootstrap|doctor|sync|candidates|run] [args...]",
            file=sys.stderr,
        )
        return 1

    command = [sys.executable, "-m", "app.main", command_name, *extra_args]
    result = subprocess.run(command, cwd=ROOT_DIR, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
