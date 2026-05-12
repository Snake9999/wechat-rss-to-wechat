from __future__ import annotations

import re


def build_cover_prompt(title: str, markdown: str, source_name: str) -> str:
    summary = summarize_markdown(markdown, max_chars=220)
    return (
        "Create a professional WeChat article cover image. "
        f"Title theme: {title}. "
        f"Source context: {source_name}. "
        f"Content summary: {summary}. "
        "Style: editorial, trustworthy, modern, clean composition, strong visual hierarchy, "
        "no watermark, no brand logo, Chinese-friendly layout, leave safe area for headline text. "
        "Aspect ratio close to 16:9."
    )


def summarize_markdown(markdown: str, max_chars: int = 220) -> str:
    text = re.sub(r"[`*_>#-]", " ", markdown)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."
