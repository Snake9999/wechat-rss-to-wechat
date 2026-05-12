from __future__ import annotations

from bs4 import BeautifulSoup


def clean_html(raw_html: str, keep_images: bool = False) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    for node in soup(["script", "style", "iframe", "noscript"]):
        node.decompose()

    for node in soup.select(".qr_code_pc_outer, .original_primary_card_tips"):
        node.decompose()

    if not keep_images:
        for node in soup.find_all("img"):
            node.decompose()

    for tag in soup.find_all(True):
        allowed_attrs = {}
        if keep_images and tag.name == "img":
            for attr in ("src", "alt"):
                if tag.get(attr):
                    allowed_attrs[attr] = tag[attr]
        tag.attrs = allowed_attrs

    return str(soup)
