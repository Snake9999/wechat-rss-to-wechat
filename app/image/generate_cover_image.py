from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import requests
from requests import RequestException

from app.utils.file_io import write_text


def generate_cover_image(
    prompt: str,
    output_path: Path,
    model_config: dict[str, Any],
    image_config: dict[str, Any],
) -> dict[str, Any]:
    api_key = first_non_empty(
        image_config.get("api_key"),
        os.getenv("IMAGE_API_KEY", ""),
        model_config.get("api_key"),
        os.getenv("LLM_API_KEY", ""),
    )
    base_url = first_non_empty(
        image_config.get("base_url"),
        os.getenv("IMAGE_BASE_URL", ""),
        model_config.get("base_url"),
        os.getenv("LLM_BASE_URL", ""),
    )
    primary_model = first_non_empty(
        image_config.get("model"),
        os.getenv("IMAGE_MODEL", ""),
        "gpt-image-2",
    )
    fallback_models = image_config.get("fallback_models", ["gpt-image-1"])
    models_to_try = [primary_model] + [
        str(item).strip() for item in fallback_models if str(item).strip() and str(item).strip() != primary_model
    ]
    size = str(image_config.get("size", "")).strip() or "1024x1024"

    if not api_key:
        return {"ok": False, "reason": "image api key missing"}
    if not base_url:
        return {"ok": False, "reason": "image base_url missing"}

    endpoint = normalize_image_endpoint(base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    errors: list[str] = []
    error_details: list[dict[str, str]] = []
    for model in models_to_try:
        payload = {"model": model, "prompt": prompt, "size": size}
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False),
                timeout=90,
            )
        except RequestException as exc:
            return {
                "ok": False,
                "reason": f"image request exception: {exc.__class__.__name__}",
                "response": str(exc)[:500],
                "tried_models": models_to_try,
            }
        if response.status_code >= 300:
            body = response.text[:500]
            errors.append(f"{model}: {response.status_code}")
            error_details.append(
                {
                    "model": model,
                    "status_code": str(response.status_code),
                    "response": body,
                }
            )
            if "model_not_found" in body:
                continue
            return {
                "ok": False,
                "reason": f"image request failed: {response.status_code}",
                "response": body,
                "tried_models": models_to_try,
                "error_details": error_details,
            }

        data = response.json()
        items = data.get("data", [])
        if not items:
            errors.append(f"{model}: empty_data")
            continue

        first = items[0]
        if first.get("b64_json"):
            image_bytes = base64.b64decode(first["b64_json"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            return {
                "ok": True,
                "path": str(output_path),
                "model": model,
                "size": size,
                "base_url": endpoint,
                "tried_models": models_to_try,
            }

        if first.get("url"):
            try:
                image_resp = requests.get(first["url"], timeout=60)
            except RequestException as exc:
                errors.append(f"{model}: download_exception:{exc.__class__.__name__}")
                continue
            if image_resp.status_code >= 300:
                errors.append(f"{model}: download_url_failed")
                continue
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_resp.content)
            return {
                "ok": True,
                "path": str(output_path),
                "model": model,
                "size": size,
                "base_url": endpoint,
                "tried_models": models_to_try,
            }

        errors.append(f"{model}: no_b64_or_url")

    return {
        "ok": False,
        "reason": "all image models failed",
        "tried_models": models_to_try,
        "errors": errors,
        "error_details": error_details,
        "hint": "Current provider rejected all configured image models. Check which image model names your provider account actually supports, or switch image.base_url/image.api_key to a provider with available image channels.",
    }


def write_cover_prompt(prompt: str, prompt_path: Path) -> None:
    write_text(prompt_path, prompt + "\n")


def normalize_image_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/images/generations"):
        return normalized
    return f"{normalized}/images/generations"


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return ""


def download_cover_from_url(url: str, output_path: Path) -> dict[str, Any]:
    if not url:
        return {"ok": False, "reason": "source cover url missing"}

    try:
        response = requests.get(url, timeout=60)
    except RequestException as exc:
        return {
            "ok": False,
            "reason": f"source cover request exception: {exc.__class__.__name__}",
            "response": str(exc)[:200],
        }
    if response.status_code >= 300:
        return {
            "ok": False,
            "reason": f"source cover download failed: {response.status_code}",
            "response": response.text[:200],
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return {"ok": True, "path": str(output_path), "source": "source_cover_url"}
