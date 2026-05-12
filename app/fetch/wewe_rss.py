from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
import xml.etree.ElementTree as ET
from typing import Iterable
from urllib.parse import quote
from urllib.parse import urlencode

from app.models.article import ArticleMetadata
from app.utils.http import get


def fetch_available_sources(base_url: str) -> list[dict]:
    response = get(f"{base_url.rstrip('/')}/feeds")
    data = json.loads(response.text)
    if not isinstance(data, list):
        raise RuntimeError("wewe-rss /feeds did not return a list")

    sources: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id") or "").strip()
        if not source_id:
            continue
        sources.append(
            {
                "id": source_id,
                "name": str(item.get("name") or source_id).strip() or source_id,
                "intro": str(item.get("intro") or "").strip(),
                "cover": str(item.get("cover") or "").strip(),
                "sync_time": item.get("syncTime"),
                "update_time": item.get("updateTime"),
            }
        )
    return sources


def fetch_latest_articles(
    base_url: str,
    source_id: str,
    limit: int = 1,
    feed_url_templates: list[str] | None = None,
) -> list[ArticleMetadata]:
    attempted_urls: list[str] = []
    for url in _candidate_feed_urls(base_url, source_id, limit, feed_url_templates):
        attempted_urls.append(url)
        try:
            response = get(url)
        except Exception:
            continue

        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type or response.text.lstrip().startswith(("{", "[")):
            articles = _parse_json_feed(response.text, source_id)
        else:
            articles = _parse_xml_feed(response.text, source_id)

        if articles:
            return articles[:limit]

    attempted_msg = "\n".join(f"- {url}" for url in attempted_urls) or "- (none)"
    raise RuntimeError(
        f"Unable to fetch feed for source_id={source_id} from {base_url}. "
        f"Tried URLs:\n{attempted_msg}"
    )


def _candidate_feed_urls(
    base_url: str,
    source_id: str,
    limit: int,
    feed_url_templates: list[str] | None = None,
) -> Iterable[str]:
    if feed_url_templates:
        for template in feed_url_templates:
            yield _render_template(template, base_url, source_id, limit)
        return

    query = urlencode({"limit": limit})
    default_urls = [
        f"{base_url}/feeds/{source_id}.json?{query}",
        f"{base_url}/feeds/{source_id}?{query}",
        f"{base_url}/{source_id}.json?{query}",
        f"{base_url}/{source_id}?{query}",
    ]
    for url in default_urls:
        yield url


def _render_template(template: str, base_url: str, source_id: str, limit: int) -> str:
    escaped_source_id = quote(source_id, safe="")
    query = urlencode({"limit": limit})
    return (
        template.replace("{base_url}", base_url.rstrip("/"))
        .replace("{source_id}", source_id)
        .replace("{source_id_escaped}", escaped_source_id)
        .replace("{limit}", str(limit))
        .replace("{query}", query)
    )


def _parse_json_feed(payload: str, source_id: str) -> list[ArticleMetadata]:
    data = json.loads(payload)
    if isinstance(data, dict):
        items = data.get("items") or data.get("entries") or data.get("data") or []
        source_name = (
            data.get("title")
            or data.get("source_name")
            or data.get("name")
            or source_id
        )
    else:
        items = data
        source_name = source_id

    articles: list[ArticleMetadata] = []
    for item in items:
        title = item.get("title") or ""
        url = item.get("url") or item.get("link") or ""
        item_id = item.get("id") or item.get("guid") or _item_id_from_url(url)
        if not title or not url or not item_id:
            continue
        articles.append(
            ArticleMetadata(
                source_id=source_id,
                source_name=item.get("source_name") or source_name,
                item_id=item_id,
                title=title,
                url=url,
                published_at=item.get("published_at")
                or item.get("date_published")
                or item.get("date_modified")
                or item.get("updated")
                or "",
            )
        )
    return articles


def _parse_xml_feed(payload: str, source_id: str) -> list[ArticleMetadata]:
    root = ET.fromstring(payload)
    channel_title = _find_text(root, ".//channel/title") or _find_text(root, ".//{*}title") or source_id
    articles: list[ArticleMetadata] = []

    for item in root.findall(".//item") + root.findall(".//{*}entry"):
        title = _find_text(item, "./title") or _find_text(item, "./{*}title") or ""
        url = (
            _find_text(item, "./link")
            or item.findtext("./{*}link")
            or _feed_link_href(item)
            or ""
        )
        item_id = (
            _find_text(item, "./guid")
            or _find_text(item, "./id")
            or _find_text(item, "./{*}id")
            or _item_id_from_url(url)
        )
        if not title or not url or not item_id:
            continue
        articles.append(
            ArticleMetadata(
                source_id=source_id,
                source_name=channel_title,
                item_id=item_id,
                title=title,
                url=url,
                published_at=(
                    _find_text(item, "./pubDate")
                    or _find_text(item, "./published")
                    or _find_text(item, "./updated")
                    or _find_text(item, "./{*}published")
                    or _find_text(item, "./{*}updated")
                    or ""
                ),
            )
        )
    return articles


def _find_text(node: ET.Element, path: str) -> str | None:
    child = node.find(path)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _feed_link_href(node: ET.Element) -> str:
    for child in node.findall("./{*}link"):
        href = child.attrib.get("href")
        if href:
            return href
    return ""


def _item_id_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def parse_published_timestamp(value: str) -> float:
    if not value:
        return 0.0
    text = value.strip()
    if not text:
        return 0.0

    # RFC3339-like
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass

    # Unix seconds string
    if text.isdigit():
        try:
            ts = int(text)
            # Heuristic for milliseconds.
            if ts > 10_000_000_000:
                ts = ts // 1000
            return float(ts)
        except Exception:
            return 0.0
    return 0.0
