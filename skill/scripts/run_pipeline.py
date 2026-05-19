#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
ACTION_MAP = {
    "prepare": "prepare",
    "bootstrap": "bootstrap",
    "doctor": "doctor",
    "sync": "sync-sources",
    "candidates": "daily-candidates",
    "run": "run-once",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the public wechat-rss-to-wechat pipeline wrapper.",
    )
    parser.add_argument(
        "action",
        choices=sorted(ACTION_MAP.keys()),
        help="Pipeline action to run",
    )
    parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the underlying app.main command",
    )
    return parser


def validate_action(action: str, extra_args: list[str]) -> None:
    if action != "run":
        return

    has_source = "--source" in extra_args
    has_item_id = "--item-id" in extra_args
    if has_source and has_item_id:
        return

    raise SystemExit(
        "[FAIL] public skill wrapper requires both --source and --item-id for `run`.\n"
        "Generate candidates first, let a human choose an item, then rerun:\n"
        "  python skill/scripts/run_pipeline.py candidates\n"
        "  python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --dry-run\n",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    extra_args = list(args.extra_args or [])
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    validate_action(args.action, extra_args)
    command_name = ACTION_MAP[args.action]
    command = [sys.executable, "-m", "app.main", command_name, *extra_args]
    result = subprocess.run(command, cwd=ROOT_DIR, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
