#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


DEFAULT_SKILL_NAME = "wechat-rss-to-wechat"
SKILL_DIR = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Link this repo's skill/ directory into an agent skill discovery directory.",
    )
    parser.add_argument(
        "--target-dir",
        required=True,
        help="Agent skill directory, for example ~/.codex/skills or ~/.claude/skills",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_SKILL_NAME,
        help=f"Installed skill name inside the target directory. Default: {DEFAULT_SKILL_NAME}",
    )
    return parser


def install_link(target_dir: Path, skill_name: str) -> int:
    target_path = target_dir.expanduser() / skill_name
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() or target_path.is_symlink():
        if target_path.resolve() == SKILL_DIR.resolve():
            print(f"[OK] skill already linked: {target_path} -> {SKILL_DIR}")
            return 0
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()
        else:
            shutil.rmtree(target_path)

    try:
        os.symlink(SKILL_DIR, target_path, target_is_directory=True)
        print(f"[OK] linked skill: {target_path} -> {SKILL_DIR}")
        print("[NEXT] restart or open a new session in your agent so the skill list refreshes")
        return 0
    except OSError as exc:
        print(f"[WARN] failed to create symlink automatically: {exc}")
        print(f"[NEXT] create a manual link from {target_path} to {SKILL_DIR}")
        return 1


def main() -> int:
    args = build_parser().parse_args()
    return install_link(Path(args.target_dir), args.name)


if __name__ == "__main__":
    raise SystemExit(main())
