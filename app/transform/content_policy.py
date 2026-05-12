from __future__ import annotations

from typing import Any


DEFAULT_FOOTER_MARKERS = [
    "推荐阅读",
    "欢迎订阅",
    "关注",
    "阅读原文",
    "END",
    "作者",
    "来源",
    "责编",
    "声明",
]

STRONG_FOOTER_MARKERS = [
    "推荐阅读",
    "阅读原文",
    "最新标准在哪查询",
    "它能帮你做什么",
    "一站式资料中心",
    "2分钟直达原文",
    "100+培训课件",
    "可随时查询下载",
    "点击图片免费试用",
    "点击“阅读原文”",
    "点击图片",
    "视频号",
    "注册用户",
    "付费用户",
]


def apply_content_policy(markdown: str, content_config: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    cfg = content_config or {}
    strip_footer = bool(cfg.get("strip_footer", True))
    markers = cfg.get("footer_cut_markers", DEFAULT_FOOTER_MARKERS)
    unified_footer = str(cfg.get("unified_footer", "")).strip()

    result = markdown
    cut_index = None

    if strip_footer:
        result, cut_index = strip_footer_tail(result, markers)

    if unified_footer:
        result = result.rstrip() + "\n\n" + unified_footer + "\n"

    return result, {
        "strip_footer": strip_footer,
        "footer_cut_index": cut_index,
        "unified_footer_applied": bool(unified_footer),
    }


def strip_footer_tail(markdown: str, markers: list[str]) -> tuple[str, int | None]:
    lines = markdown.splitlines()
    if not lines:
        return markdown, None

    marker_values = [str(item).strip() for item in markers if str(item).strip()]
    if not marker_values:
        return markdown, None

    strong_start = max(0, len(lines) - max(20, int(len(lines) * 0.6)))
    for idx in range(strong_start, len(lines)):
        line = lines[idx]
        if any(marker in line for marker in STRONG_FOOTER_MARKERS):
            kept = "\n".join(lines[:idx]).rstrip() + "\n"
            return kept, idx

    start = max(0, len(lines) - max(12, int(len(lines) * 0.35)))
    cut_index = None
    for idx in range(start, len(lines)):
        line = lines[idx]
        if any(marker in line for marker in marker_values):
            cut_index = idx
            break

    if cut_index is None:
        return markdown, None

    kept = "\n".join(lines[:cut_index]).rstrip() + "\n"
    return kept, cut_index
