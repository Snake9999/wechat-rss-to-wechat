from pathlib import Path

from app.transform.rewrite_article import maybe_rewrite_markdown

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_rewrite_retries_on_retryable_failure(monkeypatch):
    calls = {"count": 0}

    def fake_run_chat_completion(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return "", {
                "ok": False,
                "reason": "llm request failed: 503",
                "response": "temporary unavailable",
                "retryable": True,
            }
        return "2026年检查启动，覆盖259家机构，完成率95%。", {"ok": True, "retryable": False}

    monkeypatch.setattr("app.transform.rewrite_article.run_chat_completion", fake_run_chat_completion)
    monkeypatch.setattr("app.transform.rewrite_article.time.sleep", lambda _: None)

    rewritten, meta, quality = maybe_rewrite_markdown(
        markdown="检查时间是2026年，涉及259家机构，完成率95%。",
        title="测试标题",
        source_name="测试源",
        source_url="https://example.com",
        root_dir=ROOT_DIR,
        enabled=True,
        rewrite_config={"max_attempts": 3, "quality": {}},
        model_config={"api_key": "test", "base_url": "https://example.com/v1", "default": "gpt-test"},
    )

    assert rewritten.startswith("2026年检查启动")
    assert meta["rewritten"] is True
    assert meta["attempts"] == 2
    assert quality["passed"] is True


def test_rewrite_retries_when_quality_fails(monkeypatch):
    responses = iter(
        [
            ("监督检查已经启动，涉及很多机构。", {"ok": True, "retryable": False}),
            ("2026年监督检查启动，涉及259家机构，完成率95%。", {"ok": True, "retryable": False}),
        ]
    )

    monkeypatch.setattr("app.transform.rewrite_article.run_chat_completion", lambda **kwargs: next(responses))
    monkeypatch.setattr("app.transform.rewrite_article.time.sleep", lambda _: None)

    rewritten, meta, quality = maybe_rewrite_markdown(
        markdown="检查时间是2026年，涉及259家机构，完成率95%。",
        title="测试标题",
        source_name="测试源",
        source_url="https://example.com",
        root_dir=ROOT_DIR,
        enabled=True,
        rewrite_config={
            "max_attempts": 2,
            "retry_on_quality_fail": True,
            "quality": {"require_numbers_consistency": True, "max_missing_numbers": 0},
        },
        model_config={"api_key": "test", "base_url": "https://example.com/v1", "default": "gpt-test"},
    )

    assert rewritten.startswith("2026年监督检查启动")
    assert meta["rewritten"] is True
    assert meta["attempts"] == 2
    assert quality["passed"] is True


def test_rewrite_required_failure_returns_reason(monkeypatch):
    monkeypatch.setattr(
        "app.transform.rewrite_article.run_chat_completion",
        lambda **kwargs: (
            "",
            {"ok": False, "reason": "llm request failed: 503", "response": "down", "retryable": True},
        ),
    )
    monkeypatch.setattr("app.transform.rewrite_article.time.sleep", lambda _: None)

    rewritten, meta, quality = maybe_rewrite_markdown(
        markdown="检查时间是2026年，涉及259家机构。",
        title="测试标题",
        source_name="测试源",
        source_url="https://example.com",
        root_dir=ROOT_DIR,
        enabled=True,
        rewrite_config={"max_attempts": 2, "quality": {}},
        model_config={"api_key": "test", "base_url": "https://example.com/v1", "default": "gpt-test"},
    )

    assert rewritten == "检查时间是2026年，涉及259家机构。"
    assert meta["rewritten"] is False
    assert meta["attempts"] == 2
    assert "503" in meta["reason"]
    assert quality["passed"] is True
