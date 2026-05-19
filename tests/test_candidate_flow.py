import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.main import (
    build_daily_candidates_markdown,
    build_daily_candidates_report,
    build_cover_log_entry,
    build_markdown_summary,
    merge_source_configs,
    select_article,
)
from app.models.article import ArticleMetadata


class FakeProcessedStore:
    def __init__(self, processed_keys: set[tuple[str, str]]):
        self.processed_keys = processed_keys

    def has_processed(self, source_id: str, item_id: str) -> bool:
        return (source_id, item_id) in self.processed_keys


class CandidateFlowTests(unittest.TestCase):
    def iso_hours_ago(self, hours: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    def iso_days_ago(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    def make_settings(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        return SimpleNamespace(
            wewe_rss_base_url="http://localhost:4000",
            state_dir=Path(tmp_dir.name),
            output_dir=Path(tmp_dir.name) / "output",
        )

    def test_select_article_skips_processed_and_falls_through_recent_items(self):
        settings = self.make_settings()
        pipeline_config = {
            "pipeline": {"fetch_limit": 5},
            "freshness": {"max_age_hours": 48, "pick_mode": "latest"},
        }
        articles = [
            ArticleMetadata(
                source_id="source-a",
                source_name="源A",
                item_id="item-1",
                title="第一篇",
                url="https://example.com/1",
                published_at=self.iso_hours_ago(1),
            ),
            ArticleMetadata(
                source_id="source-a",
                source_name="源A",
                item_id="item-2",
                title="第二篇",
                url="https://example.com/2",
                published_at=self.iso_hours_ago(2),
            ),
        ]

        with patch("app.main.fetch_latest_articles", return_value=articles), patch(
            "app.main.ProcessedArticleStore",
            return_value=FakeProcessedStore({("source-a", "item-1")}),
        ):
            selected = select_article(
                settings=settings,
                pipeline_config=pipeline_config,
                source_id="source-a",
                item_id="",
                feed_templates=[],
                skip_processed=True,
            )

        self.assertEqual(selected.item_id, "item-2")

    def test_build_daily_candidates_report_merges_multiple_sources(self):
        settings = self.make_settings()
        pipeline_config = {
            "pipeline": {"fetch_limit": 3},
            "freshness": {"max_age_hours": 48, "pick_mode": "latest"},
        }

        def fake_fetch(_base_url, source_id, limit=1, feed_url_templates=None):
            mapping = {
                "source-a": [
                    ArticleMetadata(
                        source_id="source-a",
                        source_name="源A",
                        item_id="a-1",
                        title="源A 最新",
                        url="https://example.com/a1",
                        published_at=self.iso_hours_ago(2),
                    ),
                ],
                "source-b": [
                    ArticleMetadata(
                        source_id="source-b",
                        source_name="源B",
                        item_id="b-1",
                        title="源B 更新",
                        url="https://example.com/b1",
                        published_at=self.iso_hours_ago(1),
                    ),
                    ArticleMetadata(
                        source_id="source-b",
                        source_name="源B",
                        item_id="b-old",
                        title="源B 旧文",
                        url="https://example.com/b-old",
                        published_at=self.iso_days_ago(10),
                    ),
                ],
            }
            return mapping[source_id][:limit]

        with patch("app.main.get_pipeline_source_ids", return_value=["source-a", "source-b"]), patch(
            "app.main.fetch_latest_articles",
            side_effect=fake_fetch,
        ), patch(
            "app.main.ProcessedArticleStore",
            return_value=FakeProcessedStore(set()),
        ):
            report = build_daily_candidates_report(
                settings=settings,
                pipeline_config=pipeline_config,
                source_id=None,
                feed_templates=[],
                skip_processed=True,
            )

        self.assertEqual(report["summary"]["candidate_count"], 2)
        self.assertEqual(report["summary"]["skipped_count"], 1)
        self.assertEqual(report["candidates"][0]["item_id"], "b-1")
        self.assertEqual(report["candidates"][1]["item_id"], "a-1")
        self.assertEqual(report["skipped"][0]["skip_reason"], "stale")

    def test_select_article_by_item_id_returns_exact_match(self):
        settings = self.make_settings()
        pipeline_config = {
            "pipeline": {"fetch_limit": 5},
            "freshness": {"max_age_hours": 48, "pick_mode": "latest"},
        }
        articles = [
            ArticleMetadata(
                source_id="source-a",
                source_name="源A",
                item_id="item-1",
                title="第一篇",
                url="https://example.com/1",
                published_at=self.iso_hours_ago(1),
            ),
            ArticleMetadata(
                source_id="source-a",
                source_name="源A",
                item_id="item-2",
                title="第二篇",
                url="https://example.com/2",
                published_at=self.iso_hours_ago(2),
            ),
        ]

        with patch("app.main.fetch_latest_articles", return_value=articles), patch(
            "app.main.ProcessedArticleStore",
            return_value=FakeProcessedStore(set()),
        ):
            selected = select_article(
                settings=settings,
                pipeline_config=pipeline_config,
                source_id="source-a",
                item_id="item-2",
                feed_templates=[],
                skip_processed=True,
            )

        self.assertEqual(selected.title, "第二篇")

    def test_build_markdown_summary_skips_title_and_truncates_body(self):
        markdown = (
            "# 真正标题\n\n"
            "第一段说明这篇文章主要在讲一周候选窗口下的监管动态和执行要求。\n\n"
            "第二段继续补充更多判断信息。"
        )

        summary = build_markdown_summary(markdown, "真正标题", max_chars=30)

        self.assertNotIn("真正标题", summary)
        self.assertTrue(summary.startswith("第一段说明这篇文章主要在讲"))
        self.assertLessEqual(len(summary), 33)

    def test_merge_source_configs_keeps_existing_profiles_and_adds_discovered_meta(self):
        existing_sources = [
            {
                "id": "source-a",
                "name": "旧名字",
                "enabled": False,
                "rewrite_profile": "custom",
                "cover_profile": "alert",
            }
        ]
        discovered_sources = [
            {
                "id": "source-a",
                "name": "新名字",
                "intro": "发现到的简介",
                "cover": "https://example.com/a.jpg",
            },
            {
                "id": "source-b",
                "name": "源B",
                "intro": "源B简介",
                "cover": "https://example.com/b.jpg",
            },
        ]

        merged = merge_source_configs(existing_sources, discovered_sources)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["id"], "source-a")
        self.assertEqual(merged[0]["name"], "新名字")
        self.assertFalse(merged[0]["enabled"])
        self.assertEqual(merged[0]["rewrite_profile"], "custom")
        self.assertEqual(merged[0]["cover_profile"], "alert")
        self.assertEqual(merged[0]["intro"], "发现到的简介")
        self.assertEqual(merged[1]["id"], "source-b")
        self.assertTrue(merged[1]["enabled"])
        self.assertEqual(merged[1]["rewrite_profile"], "default")
        self.assertEqual(merged[1]["cover_profile"], "news-tech")

    def test_daily_candidates_report_can_include_summaries(self):
        settings = self.make_settings()
        pipeline_config = {
            "pipeline": {"fetch_limit": 3},
            "freshness": {"max_age_hours": 48, "pick_mode": "latest"},
            "content": {"strip_footer": True},
        }
        article = ArticleMetadata(
            source_id="source-a",
            source_name="源A",
            item_id="a-1",
            title="源A 最新",
            url="https://example.com/a1",
            published_at=self.iso_hours_ago(1),
        )

        with patch("app.main.get_pipeline_source_ids", return_value=["source-a"]), patch(
            "app.main.fetch_latest_articles",
            return_value=[article],
        ), patch(
            "app.main.ProcessedArticleStore",
            return_value=FakeProcessedStore(set()),
        ), patch(
            "app.main.extract_article",
            return_value=SimpleNamespace(content_html="<p>第一段摘要信息</p><p>第二段说明</p>"),
        ):
            report = build_daily_candidates_report(
                settings=settings,
                pipeline_config=pipeline_config,
                source_id=None,
                feed_templates=[],
                skip_processed=True,
                include_summary=True,
            )

        self.assertEqual(report["summary"]["candidate_count"], 1)
        self.assertIn("第一段摘要信息", report["candidates"][0]["summary"])

    def test_build_daily_candidates_markdown_renders_human_readable_list(self):
        report = {
            "generated_at": "2026-05-12T05:10:00+08:00",
            "config": {"max_age_hours": 168},
            "summary": {"candidate_count": 1, "skipped_count": 1},
            "candidates": [
                {
                    "rank": 1,
                    "title": "测试标题",
                    "source_name": "测试源",
                    "age_hours": 12.5,
                    "summary": "这里是一段摘要。",
                    "source_id": "source-a",
                    "item_id": "item-1",
                }
            ],
            "skipped": [
                {
                    "title": "已处理旧文",
                    "skip_reason": "processed",
                }
            ],
        }

        markdown = build_daily_candidates_markdown(report)

        self.assertIn("# 今日选题", markdown)
        self.assertIn("生成时间：2026-05-12T05:10:00+08:00", markdown)
        self.assertIn("1. 测试标题", markdown)
        self.assertIn("摘要：这里是一段摘要。", markdown)
        self.assertIn("已处理过：", markdown)

    def test_build_cover_log_entry_keeps_model_trace(self):
        cover_entry = build_cover_log_entry(
            {
                "enabled": True,
                "generated": True,
                "ok": True,
                "path": "/tmp/cover.png",
                "model": "gpt-image-2",
                "base_url": "https://api.example.com/v1/images/generations",
                "size": "1536x1024",
                "render_size": "1536x1024",
                "output_size": "1536x658",
                "tried_models": ["gpt-image-2", "gpt-image-1"],
            }
        )

        self.assertEqual(cover_entry["source"], "ai_generated")
        self.assertEqual(cover_entry["model"], "gpt-image-2")
        self.assertEqual(cover_entry["base_url"], "https://api.example.com/v1/images/generations")
        self.assertEqual(cover_entry["tried_models"], ["gpt-image-2", "gpt-image-1"])

    def test_build_cover_log_entry_marks_source_cover_fallback(self):
        cover_entry = build_cover_log_entry(
            {
                "enabled": True,
                "generated": True,
                "path": "/tmp/source-cover.jpg",
                "fallback_used": "source_cover_url",
            }
        )

        self.assertEqual(cover_entry["source"], "source_cover_url")
        self.assertEqual(cover_entry["fallback_used"], "source_cover_url")


if __name__ == "__main__":
    unittest.main()
