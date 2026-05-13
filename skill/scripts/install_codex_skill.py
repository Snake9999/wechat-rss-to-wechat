#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from install_skill_link import DEFAULT_SKILL_NAME, install_link


def main() -> int:
    return install_link(Path.home() / ".codex" / "skills", DEFAULT_SKILL_NAME)


if __name__ == "__main__":
    raise SystemExit(main())
