from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.models.article import ExtractedArticle
from app.utils.http import get


def extract_article(url: str) -> ExtractedArticle:
    response = get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    content_node = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    if content_node is None:
        raise RuntimeError("Unable to locate WeChat article content container")

    title = (
        _meta_content(soup, "og:title")
        or _text(soup.select_one("#activity-name"))
        or _text(soup.select_one("title"))
        or "Untitled WeChat Article"
    )
    author = _text(soup.select_one("#js_name")) or _meta_content(soup, "author") or ""
    cover_image_url = _meta_content(soup, "og:image") or ""
    published_at = _extract_publish_time(response.text)

    return ExtractedArticle(
        title=title,
        content_html=str(content_node),
        source_url=url,
        cover_image_url=cover_image_url,
        author=author,
        published_at=published_at,
    )


def _meta_content(soup: BeautifulSoup, prop: str) -> str:
    node = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    if node and node.get("content"):
        return node["content"].strip()
    return ""


def _text(node) -> str:
    if node is None:
        return ""
    return node.get_text(strip=True)


def _extract_publish_time(html: str) -> str:
    patterns = [
        r"publish_time\s*=\s*\"([^\"]+)\"",
        r"ct\s*=\s*\"?(\d{10})\"?",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return ""
