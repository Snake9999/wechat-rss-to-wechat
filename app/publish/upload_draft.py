from __future__ import annotations

from pathlib import Path

from app.publish.md2wechat_adapter import upload_markdown


def upload_draft(run_sh: str, markdown_path: Path, cover_path: Path | None = None, dry_run: bool = False) -> dict:
    result = upload_markdown(run_sh, markdown_path, cover_path=cover_path, dry_run=dry_run)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": result.args,
    }
