from __future__ import annotations

import json
from pathlib import Path

from app.utils.file_io import ensure_parent
from app.utils.time import now_iso


def append_run_log(path: Path, payload: dict) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": now_iso(), **payload}, ensure_ascii=False) + "\n")
