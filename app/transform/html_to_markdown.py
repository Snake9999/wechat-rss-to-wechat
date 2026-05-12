from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify as to_markdown


def convert_html_to_markdown(html: str, heading_style: str = "ATX") -> str:
    markdown = to_markdown(
        html,
        heading_style=heading_style,
        bullets="-",
        strip=["style", "script"],
    )
    return _normalize_markdown(markdown)


def fallback_text_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    blocks = [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote"])]
    return "\n\n".join(block for block in blocks if block)


def _normalize_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.splitlines()]
    compacted: list[str] = []
    previous_blank = False
    for line in lines:
        blank = line == ""
        if blank and previous_blank:
            continue
        compacted.append(line)
        previous_blank = blank
    return "\n".join(compacted).strip() + "\n"
