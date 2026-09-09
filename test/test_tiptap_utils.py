"""core.tiptap 单元测试：TipTap JSON 与纯文本互转 + 历史纯文本兜底。"""

import unittest

from core.tiptap import plain_to_tiptap, tiptap_to_plain


class TiptapUtilsTest(unittest.TestCase):
    def test_plain_to_tiptap_roundtrip(self):
        doc = plain_to_tiptap("第一段\n第二段")
        self.assertEqual(tiptap_to_plain(doc), "第一段 第二段")
        parsed = __import__("json").loads(doc)
        self.assertEqual(parsed["type"], "doc")
        self.assertEqual(len(parsed["content"]), 2)

    def test_plain_to_tiptap_empty(self):
        doc = plain_to_tiptap("")
        self.assertEqual(tiptap_to_plain(doc), "")
        self.assertEqual(__import__("json").loads(doc)["content"], [{"type": "paragraph"}])

    def test_marks_and_structures(self):
        doc = __import__("json").dumps({
            "type": "doc", "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "加粗", "marks": [{"type": "bold"}]},
                    {"type": "text", "text": "斜体", "marks": [{"type": "italic"}]},
                ]},
                {"type": "bulletList", "content": [
                    {"type": "listItem", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "项"}]}],
                    }],
                }
            ],
        })
        self.assertEqual(tiptap_to_plain(doc), "加粗 斜体 项")

    def test_legacy_plain_text_passthrough(self):
        # 历史数据：描述是纯文本（非 JSON）→ 原样返回
        self.assertEqual(tiptap_to_plain("群活动说明"), "群活动说明")

    def test_invalid_json_passthrough(self):
        self.assertEqual(tiptap_to_plain("{bad json"), "{bad json")


if __name__ == "__main__":
    unittest.main()
