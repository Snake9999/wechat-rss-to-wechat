import json
import unittest

from unittest.mock import patch

from app.fetch.wewe_rss import _parse_json_feed, fetch_available_sources


class WeweRssTests(unittest.TestCase):
    def test_fetch_available_sources_reads_feed_catalog(self):
        payload = [
            {
                "id": "MP_WXS_1",
                "name": "源一",
                "intro": "简介",
                "cover": "https://example.com/cover.jpg",
                "syncTime": 123,
                "updateTime": 456,
            }
        ]

        class Response:
            text = json.dumps(payload, ensure_ascii=False)

        with patch("app.fetch.wewe_rss.get", return_value=Response()):
            sources = fetch_available_sources("http://localhost:4000")

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], "MP_WXS_1")
        self.assertEqual(sources[0]["name"], "源一")
        self.assertEqual(sources[0]["intro"], "简介")

    def test_parse_json_feed_uses_date_modified_for_published_at(self):
        payload = {
            "title": "测试源",
            "items": [
                {
                    "id": "item-1",
                    "title": "标题",
                    "url": "https://example.com/1",
                    "date_modified": "2026-05-12T10:00:00.000Z",
                }
            ],
        }

        articles = _parse_json_feed(json.dumps(payload, ensure_ascii=False), "source-a")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].published_at, "2026-05-12T10:00:00.000Z")


if __name__ == "__main__":
    unittest.main()
