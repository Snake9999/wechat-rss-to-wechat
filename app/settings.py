from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(slots=True)
class AppSettings:
    root_dir: Path
    wewe_rss_base_url: str
    md2wechat_run_sh: str
    tz: str
    sources_config_path: Path
    pipeline_config_path: Path
    state_dir: Path
    output_dir: Path


def load_settings() -> AppSettings:
    root_dir = Path(__file__).resolve().parent.parent
    load_dotenv(root_dir / ".env")
    md2wechat_run_sh = resolve_md2wechat_run_sh(
        os.getenv("MD2WECHAT_RUN_SCRIPT", os.getenv("MD2WECHAT_RUN_SH", "")),
    )
    return AppSettings(
        root_dir=root_dir,
        wewe_rss_base_url=os.getenv("WEWE_RSS_BASE_URL", "http://localhost:4000").rstrip("/"),
        md2wechat_run_sh=md2wechat_run_sh,
        tz=os.getenv("TZ", "Asia/Shanghai"),
        sources_config_path=root_dir / "config" / "sources.yaml",
        pipeline_config_path=root_dir / "config" / "pipeline.yaml",
        state_dir=root_dir / "data" / "state",
        output_dir=root_dir / "output",
    )


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_md2wechat_run_sh(raw_value: str) -> str:
    value = raw_value.strip()
    if value and "/absolute/path/to/" not in value.replace("\\", "/"):
        return value

    # Best-effort fallback for common local agent layouts.
    # Public users should still prefer an explicit MD2WECHAT_RUN_SCRIPT.
    candidates: list[str] = []
    script_names = ["run.sh", "run.cmd", "run.ps1"]
    roots = [
        Path.home() / ".cc-switch" / "skills" / "md2wechat" / "scripts",
        Path.home() / ".claude" / "skills" / "md2wechat" / "scripts",
        Path.home() / ".codex" / "skills" / "md2wechat" / "scripts",
    ]
    for root in roots:
        for script_name in script_names:
            candidates.append(str(root / script_name))
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return value
