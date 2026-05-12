from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from requests import RequestException

from app.transform.rewrite_quality import analyze_rewrite_quality

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

BUILTIN_STYLE_PROMPTS = {
    "wechat-structured": """
适用于监管通报、政策提醒、行业资讯类公众号文章：
- 开头先说清“发生了什么、为什么重要”。
- 结构化分节，优先使用“范围 / 时间 / 重点 / 应对建议”这类高信息密度小标题。
- 语言专业、克制、清晰，不喊口号，不空泛拔高。
- 优先帮助读者理解风险、节点和可执行动作。
""".strip(),
    "dan-koe": """
借鉴 md2wechat 的 Dan Koe 风格，但要保留事实准确：
- 观点要锋利、直接、接地气，但不要夸张。
- 句子尽量短，减少空话和套路话。
- 可以增强洞察和判断感，但不能改动原始事实与数字。
- 适合把信息写得更有张力，而不是写成鸡汤。
""".strip(),
}

HUMANIZER_INTENSITY_GUIDANCE = {
    "gentle": "温和处理，只删除最明显的 AI 套话、过度总结和客服式表达。",
    "medium": "平衡处理，去除常见 AI 味，同时保持行文稳定自然。",
    "aggressive": "深度处理，尽量去掉模板化节奏、空泛拔高和机械排比，但不能改变事实。",
}


def maybe_rewrite_markdown(
    markdown: str,
    title: str,
    source_name: str,
    source_url: str,
    root_dir: Path,
    enabled: bool,
    rewrite_config: dict | None = None,
    model_config: dict | None = None,
) -> tuple[str, dict, dict]:
    if not enabled:
        return markdown, {"rewritten": False, "reason": "rewrite disabled"}, default_quality_report()

    rewrite_cfg = rewrite_config or {}
    cfg = model_config or {}
    provider = str(cfg.get("provider", "")).strip() or "custom"
    model = str(cfg.get("default", "")).strip() or os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = str(cfg.get("base_url", "")).strip() or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = str(cfg.get("api_key", "")).strip() or os.getenv("LLM_API_KEY", "").strip()
    style_name = str(rewrite_cfg.get("style", "")).strip() or "wechat-structured"
    max_attempts = max(1, int(rewrite_cfg.get("max_attempts", 3)))
    retry_delay_seconds = max(0.0, float(rewrite_cfg.get("retry_delay_seconds", 2)))
    retry_on_quality_fail = bool(rewrite_cfg.get("retry_on_quality_fail", True))
    quality_config = rewrite_cfg.get("quality", {})
    humanize_cfg = rewrite_cfg.get("humanize", {}) or {}
    humanize_enabled = bool(humanize_cfg.get("enabled", False))
    humanize_intensity = str(humanize_cfg.get("intensity", "medium")).strip() or "medium"

    if not api_key:
        return markdown, {
            "rewritten": False,
            "reason": "model.api_key missing",
            "provider": provider,
            "style": style_name,
        }, default_quality_report()

    base_url = base_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_meta: dict[str, Any] = {}
    last_quality = default_quality_report()

    for attempt in range(1, max_attempts + 1):
        rewritten, meta = rewrite_once(
            markdown=markdown,
            title=title,
            source_name=source_name,
            source_url=source_url,
            root_dir=root_dir,
            model=model,
            provider=provider,
            base_url=base_url,
            headers=headers,
            style_name=style_name,
            humanize_enabled=humanize_enabled,
            humanize_intensity=humanize_intensity,
        )
        meta["attempt"] = attempt
        meta["max_attempts"] = max_attempts
        last_meta = meta

        if not meta.get("rewritten"):
            if meta.get("retryable") and attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            return markdown, finalize_failure_meta(last_meta, "rewrite_failed_after_retries"), last_quality

        last_quality = analyze_rewrite_quality(
            original_markdown=markdown,
            rewritten_markdown=rewritten,
            config=quality_config,
        )
        if last_quality.get("passed", False):
            meta["quality_passed"] = True
            meta["attempts"] = attempt
            return rewritten, meta, last_quality

        last_meta = {
            **meta,
            "rewritten": False,
            "reason": "quality_check_failed",
            "quality_passed": False,
            "quality_issues": last_quality.get("issues", []),
            "missing_numbers": last_quality.get("missing_numbers", []),
            "new_numbers": last_quality.get("new_numbers", []),
            "frequency_mismatches": last_quality.get("frequency_mismatches", []),
        }
        if retry_on_quality_fail and attempt < max_attempts:
            time.sleep(retry_delay_seconds)
            continue

        return markdown, finalize_failure_meta(last_meta, "quality_check_failed_after_retries"), last_quality

    return markdown, finalize_failure_meta(last_meta, "rewrite_failed_after_retries"), last_quality


def rewrite_once(
    markdown: str,
    title: str,
    source_name: str,
    source_url: str,
    root_dir: Path,
    model: str,
    provider: str,
    base_url: str,
    headers: dict[str, str],
    style_name: str,
    humanize_enabled: bool,
    humanize_intensity: str,
) -> tuple[str, dict[str, Any]]:
    system_prompt = build_rewrite_system_prompt(root_dir, style_name)
    user_prompt_template = load_prompt(root_dir / "prompts" / "rewrite_user.md")
    user_prompt = user_prompt_template.format(
        title=title,
        source_name=source_name,
        source_url=source_url,
        markdown=markdown,
    )

    rewritten, meta = run_chat_completion(
        model=model,
        base_url=base_url,
        headers=headers,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
    )
    if not meta.get("ok"):
        return markdown, {
            "rewritten": False,
            "reason": meta.get("reason", "rewrite request failed"),
            "response": meta.get("response", ""),
            "retryable": meta.get("retryable", False),
            "style": style_name,
            "humanized": humanize_enabled,
        }

    final_output = rewritten
    if humanize_enabled:
        humanized, humanize_meta = humanize_rewritten_markdown(
            markdown=rewritten,
            root_dir=root_dir,
            model=model,
            base_url=base_url,
            headers=headers,
            intensity=humanize_intensity,
        )
        if not humanize_meta.get("ok"):
            return markdown, {
                "rewritten": False,
                "reason": humanize_meta.get("reason", "humanize request failed"),
                "response": humanize_meta.get("response", ""),
                "retryable": humanize_meta.get("retryable", False),
                "style": style_name,
                "humanized": True,
                "humanize_intensity": humanize_intensity,
            }
        final_output = humanized

    return ensure_trailing_newline(final_output), {
        "rewritten": True,
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "style": style_name,
        "humanized": humanize_enabled,
        "humanize_intensity": humanize_intensity if humanize_enabled else "",
        "retryable": False,
    }


def humanize_rewritten_markdown(
    markdown: str,
    root_dir: Path,
    model: str,
    base_url: str,
    headers: dict[str, str],
    intensity: str,
) -> tuple[str, dict[str, Any]]:
    system_prompt = load_prompt(root_dir / "prompts" / "humanize_system.md")
    user_prompt_template = load_prompt(root_dir / "prompts" / "humanize_user.md")
    normalized_intensity = intensity if intensity in HUMANIZER_INTENSITY_GUIDANCE else "medium"
    user_prompt = user_prompt_template.format(
        intensity=normalized_intensity,
        intensity_guidance=HUMANIZER_INTENSITY_GUIDANCE[normalized_intensity],
        markdown=markdown,
    )
    return run_chat_completion(
        model=model,
        base_url=base_url,
        headers=headers,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )


def run_chat_completion(
    model: str,
    base_url: str,
    headers: dict[str, str],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False),
            timeout=45,
        )
    except RequestException as exc:
        return "", {
            "ok": False,
            "reason": f"request exception: {exc.__class__.__name__}",
            "response": str(exc)[:500],
            "retryable": True,
        }

    if response.status_code >= 300:
        return "", {
            "ok": False,
            "reason": f"llm request failed: {response.status_code}",
            "response": response.text[:500],
            "retryable": response.status_code in RETRYABLE_STATUS_CODES,
        }

    try:
        data = response.json()
    except ValueError:
        return "", {
            "ok": False,
            "reason": "invalid llm json response",
            "response": response.text[:500],
            "retryable": True,
        }

    rewritten = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not rewritten:
        return "", {
            "ok": False,
            "reason": "empty llm output",
            "response": response.text[:500],
            "retryable": True,
        }
    return rewritten, {"ok": True, "retryable": False}


def build_rewrite_system_prompt(root_dir: Path, style_name: str) -> str:
    base_prompt = load_prompt(root_dir / "prompts" / "rewrite_system.md")
    style_prompt = load_style_prompt(root_dir, style_name)
    if not style_prompt:
        return base_prompt
    return f"{base_prompt}\n\n写作风格要求：\n{style_prompt}"


def load_style_prompt(root_dir: Path, style_name: str) -> str:
    normalized = style_name.strip() or "wechat-structured"
    prompt_path = root_dir / "prompts" / "rewrite_styles" / f"{normalized}.md"
    if prompt_path.exists():
        return load_prompt(prompt_path)
    return BUILTIN_STYLE_PROMPTS.get(normalized, BUILTIN_STYLE_PROMPTS["wechat-structured"])


def finalize_failure_meta(meta: dict[str, Any], default_reason: str) -> dict[str, Any]:
    final_meta = dict(meta)
    final_meta["rewritten"] = False
    reason = final_meta.get("reason") or default_reason
    if reason == "quality_check_failed" and final_meta.get("quality_issues"):
        reason = f"{reason}: {'; '.join(final_meta['quality_issues'])}"
    final_meta["reason"] = reason
    final_meta["attempts"] = final_meta.get("attempt", 0)
    return final_meta


def default_quality_report() -> dict[str, Any]:
    return {"passed": True, "issues": [], "metrics": {}, "missing_numbers": []}


def ensure_trailing_newline(text: str) -> str:
    return text + ("\n" if not text.endswith("\n") else "")


def load_prompt(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
