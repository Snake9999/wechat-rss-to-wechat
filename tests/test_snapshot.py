import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.main import handle_snapshot


class SnapshotTests(unittest.TestCase):
    def test_handle_snapshot_writes_to_docs_internal_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            settings = SimpleNamespace(root_dir=root)
            args = Namespace(title="公开边界收口", summary="测试快照路径")

            with patch("app.main.load_settings", return_value=settings):
                exit_code = handle_snapshot(args)
            self.assertEqual(exit_code, 0)
            snapshot_dir = root / "docs" / "internal" / "snapshots"
            files = list(snapshot_dir.glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertIn("公开边界收口", files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
