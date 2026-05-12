from app.transform.rewrite_quality import analyze_rewrite_quality


def test_quality_passes_when_numbers_kept():
    original = "检查时间是2026年，涉及259家机构，完成率95%。"
    rewritten = "2026年监督检查启动，覆盖259家机构，完成率预计95%。"
    report = analyze_rewrite_quality(original, rewritten, {})
    assert report["passed"] is True


def test_quality_fails_when_numbers_missing():
    original = "检查时间是2026年，涉及259家机构，完成率95%。"
    rewritten = "监督检查已经启动，涉及很多机构。"
    report = analyze_rewrite_quality(original, rewritten, {})
    assert report["passed"] is False
    assert report["metrics"]["missing_numbers_count"] >= 1


def test_quality_allows_small_missing_numbers_when_threshold_set():
    original = "检查时间是2026年，涉及259家机构，完成率95%。"
    rewritten = "2026年监督检查已启动，涉及机构，完成率预计95%。"
    report = analyze_rewrite_quality(
        original,
        rewritten,
        {
            "max_missing_numbers": 1,
            "require_numbers_consistency": True,
            "enforce_number_frequency": False,
        },
    )
    assert report["passed"] is True


def test_quality_fails_when_length_ratio_too_high():
    original = "2026年检查启动，涉及259家机构。"
    rewritten = original * 5
    report = analyze_rewrite_quality(original, rewritten, {"max_length_ratio": 1.5})
    assert report["passed"] is False
    assert any("length ratio out of range" in issue for issue in report["issues"])


def test_quality_fails_when_new_numbers_are_introduced():
    original = "检查时间是2026年，涉及259家机构。"
    rewritten = "检查时间是2026年，涉及259家机构，另有300家待查。"
    report = analyze_rewrite_quality(
        original,
        rewritten,
        {"require_numbers_consistency": True, "forbid_new_numbers": True, "max_extra_numbers": 0},
    )
    assert report["passed"] is False
    assert "300" in report["new_numbers"]


def test_quality_fails_when_number_frequency_changes():
    original = "2026年检查259家机构，其中259家都要复核。"
    rewritten = "2026年检查259家机构，都要复核。"
    report = analyze_rewrite_quality(
        original,
        rewritten,
        {
            "require_numbers_consistency": True,
            "max_missing_numbers": 0,
            "enforce_number_frequency": True,
        },
    )
    assert report["passed"] is False
    assert any("259:2->1" in item for item in report["frequency_mismatches"])


def test_quality_allows_number_repeated_more_times_by_default():
    original = "2026年检查259家机构。"
    rewritten = "2026年检查259家机构，259家需复核。"
    report = analyze_rewrite_quality(
        original,
        rewritten,
        {
            "require_numbers_consistency": True,
            "max_missing_numbers": 0,
            "forbid_new_numbers": True,
            "enforce_number_frequency": True,
            "require_exact_number_frequency": False,
        },
    )
    assert report["passed"] is True


def test_quality_ignores_structural_heading_numbers_for_frequency():
    original = "# 标题\n\n**PART.1**\n\n**1.自查自纠阶段**\n\n2026年检查259家机构。"
    rewritten = "# 标题\n\n## 一、自查自纠阶段\n\n2026年检查259家机构。"
    report = analyze_rewrite_quality(
        original,
        rewritten,
        {
            "require_numbers_consistency": True,
            "max_missing_numbers": 0,
            "forbid_new_numbers": True,
            "enforce_number_frequency": True,
            "require_exact_number_frequency": False,
        },
    )
    assert report["passed"] is True
