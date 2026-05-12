import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.main import build_prepare_report


class PrepareTests(unittest.TestCase):
    def make_settings(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        root = Path(tmp_dir.name)
        env_path = root / ".env"
        pipeline_path = root / "config" / "pipeline.yaml"
        sources_path = root / "config" / "sources.yaml"
        md2wechat_run_sh = root / ".codex" / "skills" / "md2wechat" / "scripts" / "run.sh"
        pipeline_path.parent.mkdir(parents=True, exist_ok=True)
        md2wechat_run_sh.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("WEWE_RSS_BASE_URL=http://localhost:4000\n", encoding="utf-8")
        pipeline_path.write_text("pipeline: {}\n", encoding="utf-8")
        sources_path.write_text("sources: []\n", encoding="utf-8")
        md2wechat_run_sh.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        return SimpleNamespace(
            root_dir=root,
            wewe_rss_base_url="http://localhost:4000",
            md2wechat_run_sh=str(md2wechat_run_sh),
            sources_config_path=sources_path,
            pipeline_config_path=pipeline_path,
        )

    def test_build_prepare_report_flags_missing_subscription_source(self):
        settings = self.make_settings()
        pipeline_config = {"pipeline": {"feed_url_templates": ["{base_url}/feeds/{source_id}.json?{query}"]}}

        with patch("app.main.diagnose_wewe_rss_connectivity", return_value=(True, "reachable")), patch(
            "app.main.fetch_available_sources",
            return_value=[],
        ):
            report = build_prepare_report(settings, pipeline_config)

        self.assertFalse(report["ready"])
        self.assertTrue(any(label == "wewe-rss subscribed sources" and not ok for label, ok, _ in report["checks"]))
        self.assertTrue(any("订阅至少一个 WeChat source" in step or "open your wewe-rss admin" in step for step in report["next_steps"]))

    def test_build_prepare_report_marks_ready_when_all_checks_pass(self):
        settings = self.make_settings()
        pipeline_config = {"pipeline": {"feed_url_templates": ["{base_url}/feeds/{source_id}.json?{query}"]}}

        with patch("app.main.diagnose_wewe_rss_connectivity", return_value=(True, "reachable")), patch(
            "app.main.fetch_available_sources",
            return_value=[{"id": "source-a", "name": "源A"}],
        ):
            report = build_prepare_report(settings, pipeline_config)

        self.assertTrue(report["ready"])
        self.assertTrue(any(label == ".env" and ok for label, ok, _detail in report["checks"]))


if __name__ == "__main__":
    unittest.main()
