from __future__ import annotations

from collections import Counter
import re
from typing import Any


def analyze_rewrite_quality(
    original_markdown: str,
    rewritten_markdown: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or {}
    min_ratio = float(cfg.get("min_length_ratio", 0.6))
    max_ratio = float(cfg.get("max_length_ratio", 1.6))
    require_numbers = bool(cfg.get("require_numbers_consistency", True))
    max_missing_numbers = int(cfg.get("max_missing_numbers", 0))
    forbid_new_numbers = bool(cfg.get("forbid_new_numbers", True))
    enforce_number_frequency = bool(cfg.get("enforce_number_frequency", True))
    max_extra_numbers = int(cfg.get("max_extra_numbers", 0))

    original_text = normalize_markdown_text(original_markdown)
    rewritten_text = normalize_markdown_text(rewritten_markdown)

    original_chars = len(original_text)
    rewritten_chars = len(rewritten_text)
    length_ratio = (rewritten_chars / original_chars) if original_chars else 0.0

    original_numbers = extract_significant_number_tokens(original_markdown)
    rewritten_numbers = extract_significant_number_tokens(rewritten_markdown)
    original_number_counts = Counter(original_numbers)
    rewritten_number_counts = Counter(rewritten_numbers)
    missing_numbers = sorted(set(original_numbers) - set(rewritten_numbers))
    new_numbers = sorted(set(rewritten_numbers) - set(original_numbers))
    frequency_mismatches = collect_frequency_mismatches(
        original_number_counts,
        rewritten_number_counts,
        require_exact_frequency=bool(cfg.get("require_exact_number_frequency", False)),
    )

    issues: list[str] = []
    passed = True

    if rewritten_chars == 0:
        passed = False
        issues.append("rewritten text is empty")

    if original_chars > 0 and (length_ratio < min_ratio or length_ratio > max_ratio):
        passed = False
        issues.append(
            f"length ratio out of range: {length_ratio:.2f} not in [{min_ratio:.2f}, {max_ratio:.2f}]"
        )

    if require_numbers and len(missing_numbers) > max_missing_numbers:
        passed = False
        preview = ", ".join(missing_numbers[:12])
        issues.append(
            "numbers missing in rewritten text exceed threshold "
            f"({len(missing_numbers)} > {max_missing_numbers}): {preview}"
        )

    if require_numbers and forbid_new_numbers and len(new_numbers) > max_extra_numbers:
        passed = False
        preview = ", ".join(new_numbers[:12])
        issues.append(
            "new numbers introduced in rewritten text exceed threshold "
            f"({len(new_numbers)} > {max_extra_numbers}): {preview}"
        )

    if require_numbers and enforce_number_frequency and frequency_mismatches:
        passed = False
        preview = ", ".join(frequency_mismatches[:12])
        issues.append(f"number frequency mismatch detected: {preview}")

    return {
        "passed": passed,
        "issues": issues,
        "metrics": {
            "original_chars": original_chars,
            "rewritten_chars": rewritten_chars,
            "length_ratio": round(length_ratio, 4),
            "original_numbers_count": len(original_numbers),
            "rewritten_numbers_count": len(rewritten_numbers),
            "missing_numbers_count": len(missing_numbers),
            "new_numbers_count": len(new_numbers),
            "frequency_mismatch_count": len(frequency_mismatches),
        },
        "missing_numbers": missing_numbers[:100],
        "new_numbers": new_numbers[:100],
        "frequency_mismatches": frequency_mismatches[:100],
    }


def normalize_markdown_text(markdown: str) -> str:
    text = re.sub(r"[`*_>#-]", " ", markdown)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_number_tokens(text: str) -> list[str]:
    # Keep integers/decimals with optional percent sign for fact consistency checks.
    tokens = re.findall(r"\d+(?:\.\d+)?%?", text)
    return [token.strip() for token in tokens if token.strip()]


def extract_significant_number_tokens(markdown: str) -> list[str]:
    tokens: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized = re.sub(r"^[\s#>*_`-]+", "", line).strip()
        normalized = re.sub(r"[*_`]+$", "", normalized).strip()
        if _is_structural_number_heading(normalized):
            continue

        tokens.extend(extract_number_tokens(normalized))
    return tokens


def _is_structural_number_heading(line: str) -> bool:
    if re.fullmatch(r"PART\.\d+", line, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"\d+[.、)]\s*.*", line):
        return True
    return False


def collect_frequency_mismatches(
    original_counts: Counter[str],
    rewritten_counts: Counter[str],
    require_exact_frequency: bool = False,
) -> list[str]:
    mismatches: list[str] = []
    for token in sorted(set(original_counts) | set(rewritten_counts)):
        original_count = original_counts.get(token, 0)
        rewritten_count = rewritten_counts.get(token, 0)
        if require_exact_frequency and original_count != rewritten_count:
            mismatches.append(f"{token}:{original_count}->{rewritten_count}")
        elif not require_exact_frequency and rewritten_count < original_count:
            mismatches.append(f"{token}:{original_count}->{rewritten_count}")
    return mismatches
