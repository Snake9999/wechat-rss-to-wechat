from pathlib import Path

from app.image.wechat_cover import (
    build_cover_payload,
    build_cover_asset_stem,
    build_prompt_from_payload,
    get_cover_schema_path,
    resolve_variant_output_size,
    resolve_variant_render_size,
    validate_cover_payload,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_build_cover_payload_uses_profile_and_language_defaults():
    payload, assumptions = build_cover_payload(
        title="示例行业检查启动",
        markdown="# 示例行业检查启动\n\n259家机构进入抽查范围，即日起开展复核。",
        source_name="示例公众号",
        cover_config={
            "profiles": {
                "news-tech": {"style": "swiss", "accent": "ikb", "variant": "wechat-21x9"}
            }
        },
        cover_profile="news-tech",
    )

    assert payload["style"] == "swiss"
    assert payload["accent"] == "ikb"
    assert payload["variant"] == "wechat-21x9"
    assert payload["language"] == "zh-CN"
    assert payload["keywords"]
    assert isinstance(assumptions, list)


def test_validate_cover_payload_rejects_editorial_non_none_accent():
    payload = {
        "title": "测试标题",
        "style": "editorial",
        "accent": "ikb",
        "variant": "wechat-21x9",
        "language": "zh-CN",
    }
    try:
        validate_cover_payload(payload, get_cover_schema_path(ROOT_DIR))
    except ValueError as exc:
        assert "accent" in str(exc)
    else:
        raise AssertionError("expected validation to fail")


def test_build_prompt_from_payload_returns_template_and_prompt():
    payload = {
        "title": "监管风暴",
        "subtitle": "259家机构进入复核名单",
        "keywords": ["监管", "抽查", "机动车检测"],
        "style": "swiss",
        "accent": "safety-orange",
        "variant": "wechat-21x9",
        "language": "zh-CN",
    }
    result = build_prompt_from_payload(ROOT_DIR, payload)
    assert result["template_id"] == "swiss.wechat-21x9"
    assert "Swiss International Typographic Style" in result["final_prompt"]


def test_cover_asset_stem_includes_variant_style_and_accent():
    stem = build_cover_asset_stem(
        "article-slug",
        {"variant": "wechat-21x9", "style": "swiss", "accent": "safety-orange"},
    )
    assert stem == "article-slug.wechat-21x9.swiss.safety-orange"


def test_variant_sizes_distinguish_render_from_output():
    cover_config = {
        "render_sizes": {"wechat-21x9": "1536x1024"},
        "output_sizes": {"wechat-21x9": "1536x658"},
    }
    image_config = {"size": "1024x1024"}

    assert resolve_variant_render_size("wechat-21x9", cover_config, image_config) == "1536x1024"
    assert resolve_variant_output_size("wechat-21x9", cover_config, image_config) == "1536x658"
