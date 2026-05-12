from __future__ import annotations

from pathlib import Path

from app.state.store import JsonStore
from app.utils.time import now_iso


class ProcessedArticleStore:
    def __init__(self, path: Path):
        self.store = JsonStore(path)

    def has_processed(self, source_id: str, item_id: str) -> bool:
        return any(
            record.get("source_id") == source_id and record.get("item_id") == item_id
            for record in self.store.load()
        )

    def mark(self, source_id: str, item_id: str, title: str, url: str, status: str) -> None:
        records = self.store.load()
        records = [
            record
            for record in records
            if not (
                record.get("source_id") == source_id and record.get("item_id") == item_id
            )
        ]
        records.append(
            {
                "source_id": source_id,
                "item_id": item_id,
                "title": title,
                "url": url,
                "status": status,
                "updated_at": now_iso(),
            }
        )
        self.store.save(records)
