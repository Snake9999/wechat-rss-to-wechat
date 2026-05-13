import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

from app.main import diagnose_wewe_rss_connectivity
from app.settings import resolve_md2wechat_run_sh


class DiagnoseWeweRssConnectivityTests(unittest.TestCase):
    def test_reports_reachable(self):
        with patch("app.main.get", lambda url, timeout=3: object()):
            ok, detail = diagnose_wewe_rss_connectivity(
                "http://localhost:4000",
                {"pipeline": {"feed_url_templates": ["{base_url}/feeds/{source_id}.json?{query}"]}},
            )

        self.assertTrue(ok)
        self.assertIn("reachable", detail)

    def test_reports_lan_hint_for_localhost(self):
        with patch("app.main.get", side_effect=RuntimeError("connection failed")):
            ok, detail = diagnose_wewe_rss_connectivity(
                "http://localhost:4000",
                {"pipeline": {"feed_url_templates": ["{base_url}/feeds/{source_id}.json?{query}"]}},
            )

        self.assertFalse(ok)
        self.assertIn("LAN URL", detail)
        self.assertIn("sandboxed agent", detail)
        self.assertIn("unreachable", detail)

    def test_resolve_md2wechat_run_sh_uses_generic_home_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)
            candidate = home / ".codex" / "skills" / "md2wechat" / "scripts" / "run.sh"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            with patch("pathlib.Path.home", return_value=home):
                resolved = resolve_md2wechat_run_sh("")

        self.assertEqual(resolved, str(candidate))

    def test_resolve_md2wechat_run_sh_accepts_windows_script_candidates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)
            candidate = home / ".codex" / "skills" / "md2wechat" / "scripts" / "run.cmd"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text("@echo off\r\n", encoding="utf-8")

            with patch("pathlib.Path.home", return_value=home):
                resolved = resolve_md2wechat_run_sh("")

        self.assertEqual(resolved, str(candidate))


if __name__ == "__main__":
    unittest.main()
