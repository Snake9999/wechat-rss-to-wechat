from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class RunResult:
    ok: bool
    status: str
    article_id: str = ""
    message: str = ""
    outputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
