"""TipTap 文档 JSON 与纯文本互转（活动描述、议事厅正文共用）。

TipTap JSON 是数据而非 HTML，渲染端（RichText.render）只认白名单节点类型并全程转义，
因此存储层可信任客户端提交的结构；本模块只做纯文本抽取与纯文本→JSON 的兜底转换。
"""

import json
from typing import Any


def _extract_text(node: Any) -> str:
    """递归遍历 TipTap document JSON，提取所有 text 节点的文本，空白归一。"""
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return " ".join(_extract_text(v) for v in node.get("content", []) if v is not None)
    if isinstance(node, list):
        return " ".join(_extract_text(item) for item in node if item is not None)
    return ""


def tiptap_to_plain(doc: Any) -> str:
    """TipTap doc JSON（dict 或 JSON 字符串）→ 纯文本。

    历史数据兜底：传入非 JSON 字符串（旧版纯文本描述）时原样返回。
    """
    if isinstance(doc, str):
        try:
            doc = json.loads(doc)
        except (TypeError, ValueError):
            return doc
    if not isinstance(doc, dict) or not doc.get("type"):
        return "" if isinstance(doc, dict) else str(doc or "")
    return _extract_text(doc).strip()


def plain_to_tiptap(text: str) -> str:
    """纯文本 → 最小 TipTap doc JSON（按换行拆段）；空文本返回单个空段落。"""
    content = [
        {"type": "paragraph", "content": [{"type": "text", "text": p}]}
        for p in (text or "").split("\n") if p.strip()
    ] or [{"type": "paragraph"}]
    return json.dumps({"type": "doc", "content": content}, ensure_ascii=False)
