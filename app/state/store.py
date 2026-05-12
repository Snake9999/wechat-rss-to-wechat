from __future__ import annotations

from pathlib import Path

from app.utils.file_io import read_json, write_json


class JsonStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[dict]:
        return read_json(self.path, default=[])

    def save(self, records: list[dict]) -> None:
        write_json(self.path, records)
