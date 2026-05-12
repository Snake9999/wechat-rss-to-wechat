import unittest

from app.transform.content_policy import apply_content_policy


class ContentPolicyTests(unittest.TestCase):
    def test_strip_footer_cuts_recommendation_block_before_marketing_tail(self):
        markdown = (
            "# 标题\n\n"
            "正文第一段\n\n"
            "正文第二段\n\n"
            "推荐阅读\n\n"
            "相关文章一\n\n"
            "点击图片免费试用体系管理系统\n\n"
            "**2万+注册用户   4000+付费用户**\n"
        )

        processed, meta = apply_content_policy(markdown, {"strip_footer": True})

        self.assertIn("正文第二段", processed)
        self.assertNotIn("推荐阅读", processed)
        self.assertNotIn("4000+付费用户", processed)
        self.assertIsNotNone(meta["footer_cut_index"])

    def test_strip_footer_cuts_promotional_tool_block(self):
        markdown = (
            "# 标题\n\n"
            "正文说明。\n\n"
            "最新标准在哪查询？\n\n"
            "飞检无忧文库，专为机动车检测从业者打造的一站式资料中心。\n\n"
            "2分钟直达原文：不用再翻官网、求群友;\n\n"
            "100+培训课件：新标准来了，员工培训资料同步跟上;\n"
        )

        processed, meta = apply_content_policy(markdown, {"strip_footer": True})

        self.assertEqual(processed.strip(), "# 标题\n\n正文说明。")
        self.assertIsNotNone(meta["footer_cut_index"])


if __name__ == "__main__":
    unittest.main()
