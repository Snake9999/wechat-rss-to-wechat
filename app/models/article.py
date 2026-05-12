from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ArticleMetadata:
    source_id: str
    source_name: str
    item_id: str
    title: str
    url: str
    published_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ExtractedArticle:
    title: str
    content_html: str
    source_url: str
    cover_image_url: str = ""
    author: str = ""
    published_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
