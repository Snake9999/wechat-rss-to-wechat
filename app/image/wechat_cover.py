from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from app.image.generate_cover_image import generate_cover_image
from app.utils.file_io import write_json, write_text
from app.utils.slug import slugify

DEFAULT_COVER_PROFILES = {
    "default": {"style": "swiss", "accent": "ikb", "variant": "wechat-21x9"},
    "news-tech": {"style": "swiss", "accent": "ikb", "variant": "wechat-21x9"},
    "news-alert": {"style": "swiss", "accent": "safety-orange", "variant": "wechat-21x9"},
    "editorial-share": {"style": "editorial", "accent": "none", "variant": "wechat-share-1x1"},
}

DEFAULT_VARIANT_RENDER_SIZES = {
    "wechat-21x9": "1536x1024",
    "wechat-share-1x1": "1024x1024",
}

DEFAULT_VARIANT_OUTPUT_SIZES = {
    "wechat-21x9": "1536x658",
    "wechat-share-1x1": "1024x1024",
}


def generate_wechat_cover_assets(
    *,
    root_dir: Path,
    output_dir: Path,
    slug: str,
    title: str,
    markdown: str,
    source_name: str,
    cover_config: dict[str, Any] | None,
    model_config: dict[str, Any],
    image_config: dict[str, Any],
    cover_profile: str = "",
    subtitle: str = "",
    style: str = "",
    accent: str = "",
    variant: str = "",
) -> dict[str, Any]:
    payload, assumptions = build_cover_payload(
        title=title,
        markdown=markdown,
        source_name=source_name,
        cover_config=cover_config or {},
        cover_profile=cover_profile,
        subtitle=subtitle,
        style=style,
        accent=accent,
        variant=variant,
    )
    validate_cover_payload(payload, get_cover_schema_path(root_dir))

    prompt_result = build_prompt_from_payload(root_dir, payload)
    prompt = str(prompt_result["final_prompt"]).strip()
    normalized_payload = prompt_result.get("normalized_payload", payload)
    asset_stem = build_cover_asset_stem(slug, normalized_payload)

    payload_path = output_dir / "covers" / f"{asset_stem}.cover-payload.json"
    write_json(payload_path, payload)

    prompt_path = output_dir / "covers" / f"{asset_stem}.cover-prompt.txt"
    write_text(prompt_path, prompt + "\n")

    resolved_variant = clean_string(normalized_payload.get("variant")) or clean_string(payload.get("variant"))
    render_size = resolve_variant_render_size(resolved_variant, cover_config or {}, image_config)
    output_size = resolve_variant_output_size(resolved_variant, cover_config or {}, image_config)
    generated_path = output_dir / "covers" / f"{asset_stem}.cover.png"
    raw_generated_path = generated_path
    needs_postprocess = output_size != render_size
    if needs_postprocess:
        raw_generated_path = output_dir / "covers" / f"{asset_stem}.cover.raw.png"
    image_result = generate_cover_image(
        prompt=prompt,
        output_path=raw_generated_path,
        model_config=model_config,
        image_config={**image_config, "size": render_size},
    )
    if image_result.get("ok") and needs_postprocess:
        postprocess_result = finalize_cover_variant(
            input_path=raw_generated_path,
            output_path=generated_path,
            variant=resolved_variant,
            output_size=output_size,
        )
        image_result.update(postprocess_result)
        image_result["path"] = str(generated_path)
    elif image_result.get("ok"):
        image_result["path"] = str(generated_path)
    return {
        **image_result,
        "payload": payload,
        "payload_path": str(payload_path),
        "prompt": prompt,
        "prompt_path": str(prompt_path),
        "template_id": prompt_result.get("template_id", ""),
        "assumptions": prompt_result.get("assumptions", assumptions),
        "normalized_payload": normalized_payload,
        "cover_profile": cover_profile or str((cover_config or {}).get("profile", "")).strip() or "default",
        "variant_size": output_size,
        "render_size": render_size,
        "output_size": output_size,
    }


def build_cover_payload(
    *,
    title: str,
    markdown: str,
    source_name: str,
    cover_config: dict[str, Any],
    cover_profile: str = "",
    subtitle: str = "",
    style: str = "",
    accent: str = "",
    variant: str = "",
) -> tuple[dict[str, Any], list[str]]:
    assumptions: list[str] = []
    profile_name = cover_profile or str(cover_config.get("profile", "")).strip() or "default"
    profiles = {**DEFAULT_COVER_PROFILES, **coerce_profile_map(cover_config.get("profiles", {}))}
    profile = profiles.get(profile_name, DEFAULT_COVER_PROFILES["default"])
    if profile_name not in profiles:
        assumptions.append(f"cover_profile defaulted from {profile_name} to default")

    resolved_style = clean_string(style) or clean_string(cover_config.get("style")) or profile["style"]
    resolved_variant = clean_string(variant) or clean_string(cover_config.get("variant")) or profile["variant"]
    resolved_accent = clean_string(accent) or clean_string(cover_config.get("accent")) or profile["accent"]
    if resolved_style == "editorial" and resolved_accent != "none":
        assumptions.append(f"accent coerced from {resolved_accent} to none for editorial style")
        resolved_accent = "none"
    if resolved_style == "swiss" and resolved_accent == "none":
        assumptions.append("accent coerced from none to ikb for swiss style")
        resolved_accent = "ikb"

    inferred_subtitle = clean_string(subtitle) or summarize_markdown(markdown, max_chars=42)
    if not inferred_subtitle:
        assumptions.append("subtitle omitted because no concise summary was available")

    payload: dict[str, Any] = {
        "title": clean_title(title),
        "style": resolved_style,
        "accent": resolved_accent,
        "variant": resolved_variant,
        "language": infer_language(title, inferred_subtitle),
    }
    if inferred_subtitle:
        payload["subtitle"] = inferred_subtitle
    payload["keywords"] = derive_keywords(title, inferred_subtitle, source_name)
    return payload, assumptions


def validate_cover_payload(payload: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    issues: list[str] = []
    allowed_fields = set(schema.get("properties", {}).keys())
    required_fields = list(schema.get("required", []))

    if not isinstance(payload, dict):
        raise ValueError("cover payload must be an object")

    extra_fields = sorted(set(payload.keys()) - allowed_fields)
    if extra_fields:
        issues.append(f"unexpected fields: {', '.join(extra_fields)}")

    for field in required_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"`{field}` is required")

    for field_name, field_schema in schema.get("properties", {}).items():
        if field_name not in payload:
            continue
        value = payload[field_name]
        field_type = field_schema.get("type")
        if field_type == "string":
            if not isinstance(value, str):
                issues.append(f"`{field_name}` must be a string")
                continue
            min_length = int(field_schema.get("minLength", 0))
            if len(value.strip()) < min_length:
                issues.append(f"`{field_name}` must have min length {min_length}")
            enums = field_schema.get("enum", [])
            if enums and value not in enums:
                issues.append(f"`{field_name}` must be one of: {', '.join(enums)}")
        elif field_type == "array":
            if not isinstance(value, list):
                issues.append(f"`{field_name}` must be an array")
                continue
            max_items = field_schema.get("maxItems")
            if isinstance(max_items, int) and len(value) > max_items:
                issues.append(f"`{field_name}` exceeds max items {max_items}")
            item_min_length = int(field_schema.get("items", {}).get("minLength", 0))
            for index, item in enumerate(value):
                if not isinstance(item, str) or len(item.strip()) < item_min_length:
                    issues.append(f"`{field_name}[{index}]` must be a non-empty string")

    if payload.get("style") == "editorial" and payload.get("accent") != "none":
        issues.append("`accent` must be `none` when `style` is `editorial`")

    if issues:
        raise ValueError("invalid wechat cover payload: " + "; ".join(issues))


def build_prompt_from_payload(root_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    script_path = get_cover_prompt_builder_path(root_dir)
    process = subprocess.run(
        ["node", str(script_path), "--compact"],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"wechat cover prompt builder failed: {stderr}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"wechat cover prompt builder returned invalid JSON: {exc}") from exc


def get_cover_skill_root(root_dir: Path) -> Path:
    return root_dir / "vendor" / "wechat-cover-skill"


def get_cover_schema_path(root_dir: Path) -> Path:
    return get_cover_skill_root(root_dir) / "references" / "payload-schema.json"


def get_cover_prompt_builder_path(root_dir: Path) -> Path:
    return get_cover_skill_root(root_dir) / "scripts" / "build-prompt.mjs"


def resolve_variant_render_size(
    variant: str,
    cover_config: dict[str, Any],
    image_config: dict[str, Any],
) -> str:
    configured = cover_config.get("render_sizes", {})
    if isinstance(configured, dict):
        value = clean_string(configured.get(variant))
        if value:
            return value
    legacy = cover_config.get("variant_sizes", {})
    if isinstance(legacy, dict):
        value = clean_string(legacy.get(variant))
        if value:
            return value
    value = clean_string(image_config.get("size"))
    if value:
        return value
    return DEFAULT_VARIANT_RENDER_SIZES.get(variant, "1536x1024")


def resolve_variant_output_size(
    variant: str,
    cover_config: dict[str, Any],
    image_config: dict[str, Any],
) -> str:
    configured = cover_config.get("output_sizes", {})
    if isinstance(configured, dict):
        value = clean_string(configured.get(variant))
        if value:
            return value
    value = clean_string(image_config.get("output_size"))
    if value:
        return value
    return DEFAULT_VARIANT_OUTPUT_SIZES.get(variant, "1536x1024")


def finalize_cover_variant(
    *,
    input_path: Path,
    output_path: Path,
    variant: str,
    output_size: str,
) -> dict[str, Any]:
    output_width, output_height = parse_size(output_size)
    if variant != "wechat-21x9":
        if input_path != output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(input_path.read_bytes())
            input_path.unlink(missing_ok=True)
        return {"postprocess": {"applied": input_path != output_path, "variant": variant, "output_size": output_size}}

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for wechat-21x9 cover post-processing") from exc

    with Image.open(input_path) as image:
        src_width, src_height = image.size
        target_ratio = output_width / output_height
        src_ratio = src_width / src_height

        if src_ratio > target_ratio:
            crop_width = int(round(src_height * target_ratio))
            crop_height = src_height
            left = max((src_width - crop_width) // 2, 0)
            top = 0
        else:
            crop_width = src_width
            crop_height = int(round(src_width / target_ratio))
            left = 0
            top = max((src_height - crop_height) // 2, 0)

        crop_box = (left, top, left + crop_width, top + crop_height)
        cropped = image.convert("RGBA").crop(crop_box)
        resized = cropped.resize((output_width, output_height), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        resized.save(output_path, format="PNG")

    input_path.unlink(missing_ok=True)
    return {
        "postprocess": {
            "applied": True,
            "variant": variant,
            "output_size": output_size,
            "crop_box": list(crop_box),
        }
    }


def parse_size(size: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", clean_string(size))
    if not match:
        raise ValueError(f"invalid size format: {size}")
    return int(match.group(1)), int(match.group(2))


def summarize_markdown(markdown: str, max_chars: int = 42) -> str:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    body_lines = [line for line in lines if not line.startswith("#")]
    if not body_lines:
        return ""
    text = re.sub(r"[`*_>#-]", " ", " ".join(body_lines[:4]))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars].rstrip("，,。.!！?？；;：: ")
    return trimmed


def derive_keywords(title: str, subtitle: str, source_name: str) -> list[str]:
    candidates = []
    for text in [title, subtitle, source_name]:
        if not text:
            continue
        parts = re.split(r"[，,。.!！?？；;：:\n、/|（）()【】\[\]·\-\s]+", text)
        for part in parts:
            value = clean_string(part)
            if value:
                candidates.append(value)

    unique: list[str] = []
    seen = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
        if len(unique) >= 5:
            break
    return unique or [clean_title(title)]


def infer_language(title: str, subtitle: str = "") -> str:
    text = f"{title} {subtitle}"
    return "zh-CN" if re.search(r"[\u3400-\u9fff]", text) else "en-US"


def clean_title(title: str) -> str:
    value = clean_string(title)
    if not value:
        raise ValueError("cover title is empty")
    value = re.sub(r"\s+", " ", value)
    return value


def clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def coerce_profile_map(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    profiles: dict[str, dict[str, str]] = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            continue
        profiles[str(key)] = {
            "style": clean_string(item.get("style")) or DEFAULT_COVER_PROFILES["default"]["style"],
            "accent": clean_string(item.get("accent")) or DEFAULT_COVER_PROFILES["default"]["accent"],
            "variant": clean_string(item.get("variant")) or DEFAULT_COVER_PROFILES["default"]["variant"],
        }
    return profiles


def build_cover_slug(prefix: str, title: str) -> str:
    return f"{prefix}-{slugify(title)}"


def build_cover_asset_stem(base_slug: str, payload: dict[str, Any]) -> str:
    variant = sanitize_asset_token(payload.get("variant"), fallback="variant")
    style = sanitize_asset_token(payload.get("style"), fallback="style")
    accent = sanitize_asset_token(payload.get("accent"), fallback="accent")
    return f"{base_slug}.{variant}.{style}.{accent}"


def sanitize_asset_token(value: Any, *, fallback: str) -> str:
    text = clean_string(value).lower()
    if not text:
        return fallback
    normalized = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return normalized or fallback
