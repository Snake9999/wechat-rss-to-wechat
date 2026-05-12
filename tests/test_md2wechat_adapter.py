import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

from app.publish.md2wechat_adapter import extract_markdown_title, extract_media_id, upload_markdown


class Md2WechatAdapterTests(unittest.TestCase):
    def test_extract_markdown_title_uses_first_h1(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "article.md"
            path.write_text("# 正确标题\n\n正文内容\n", encoding="utf-8")
            self.assertEqual(extract_markdown_title(path), "正确标题")

    def test_extract_media_id_reads_nested_data(self):
        payload = {
            "data": {
                "media_id": "MEDIA_ID_123",
            },
            "success": True,
        }
        self.assertEqual(extract_media_id(json.dumps(payload, ensure_ascii=False)), "MEDIA_ID_123")

    def test_upload_markdown_overrides_draft_title_before_create(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            markdown_path = tmp_path / "article.md"
            cover_path = tmp_path / "cover.png"
            markdown_path.write_text("# 真正标题\n\n正文内容\n", encoding="utf-8")
            cover_path.write_text("fake-image", encoding="utf-8")

            captured = {"draft_payload": None}

            def fake_run(command, capture_output, text, check, env):
                if "--save-draft" in command:
                    draft_path = Path(command[-1])
                    draft_path.write_text(
                        json.dumps(
                            {
                                "articles": [
                                    {
                                        "title": "Draft Article",
                                        "content": "<p>body</p>",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    return subprocess.CompletedProcess(command, 0, stdout="saved", stderr="")

                if "upload_image" in command:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=json.dumps({"data": {"media_id": "MEDIA_ID_123"}}, ensure_ascii=False),
                        stderr="",
                    )

                if "create_draft" in command:
                    draft_path = Path(command[-1])
                    captured["draft_payload"] = json.loads(draft_path.read_text(encoding="utf-8"))
                    return subprocess.CompletedProcess(command, 0, stdout="created", stderr="")

                raise AssertionError(f"unexpected command: {command}")

            with patch("app.publish.md2wechat_adapter.subprocess.run", side_effect=fake_run):
                result = upload_markdown(
                    run_sh="/tmp/mock-md2wechat-run.sh",
                    markdown_path=markdown_path,
                    cover_path=cover_path,
                    dry_run=False,
                )

            self.assertEqual(result.returncode, 0)
            self.assertIsNotNone(captured["draft_payload"])
            article = captured["draft_payload"]["articles"][0]
            self.assertEqual(article["title"], "真正标题")
            self.assertEqual(article["thumb_media_id"], "MEDIA_ID_123")


if __name__ == "__main__":
    unittest.main()
