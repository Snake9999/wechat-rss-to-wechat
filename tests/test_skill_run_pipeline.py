import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "skill" / "scripts" / "run_pipeline.py"
SPEC = importlib.util.spec_from_file_location("skill_run_pipeline", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_validate_action_allows_non_run_actions() -> None:
    MODULE.validate_action("candidates", [])


def test_validate_action_requires_source_and_item_id_for_run() -> None:
    with pytest.raises(SystemExit) as exc:
        MODULE.validate_action("run", ["--source", "demo"])

    assert "--source and --item-id" in str(exc.value)


def test_validate_action_accepts_explicit_selected_candidate() -> None:
    MODULE.validate_action("run", ["--source", "demo", "--item-id", "item-123", "--dry-run"])
