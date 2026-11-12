import re

# CQ 码：形如 [CQ:at,qq=123]；参数值内的 & [ ] , 按上游规范转义
_CQ_RE = re.compile(r"\[CQ:([A-Za-z0-9_.-]+)((?:,[^\]]*)?)\]")
_CQ_ESCAPES = (("&#44;", ","), ("&#91;", "["), ("&#93;", "]"), ("&amp;", "&"))


def _unescape(value: str) -> str:
    for escaped, raw in _CQ_ESCAPES:
        value = value.replace(escaped, raw)
    return value


def parse(message) -> list:
    """把字符串格式的 CQ 码消息切成消息段列表（数组格式原样返回）。

    上游：https://github.com/botuniverse/onebot-11/blob/master/message/string.md
    字符串格式下 `message` 是一个整体字符串，at、图片等都写在 CQ 码里。
    """
    if isinstance(message, list):
        return message
    if not isinstance(message, str):
        return []
    segments = []
    cursor = 0
    for matched in _CQ_RE.finditer(message):
        if matched.start() > cursor:
            chunk = _unescape(message[cursor:matched.start()])
            if chunk:
                segments.append({"type": "text", "data": {"text": chunk}})
        data = {}
        for pair in matched.group(2).lstrip(",").split(","):
            if not pair:
                continue
            key, _, value = pair.partition("=")
            data[key] = _unescape(value)
        segments.append({"type": matched.group(1), "data": data})
        cursor = matched.end()
    if cursor < len(message):
        chunk = _unescape(message[cursor:])
        if chunk:
            segments.append({"type": "text", "data": {"text": chunk}})
    return segments


def text(string: str) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E7%BA%AF%E6%96%87%E6%9C%AC
    return {"type": "text", "data": {"text": string}}


def image(file: str, cache=True) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E5%9B%BE%E7%89%87
    return {"type": "image", "data": {"file": file}}


def record(file: str, cache=True) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E8%AF%AD%E9%9F%B3
    return {"type": "record", "data": {"file": file, "cache": cache}}


def at(qq: int) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E6%9F%90%E4%BA%BA
    return {"type": "at", "data": {"qq": qq}}

def at_all() -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E6%9F%90%E4%BA%BA
    return {"type": "at", "data": {"qq": "all"}}

def xml(data: str) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#xml-%E6%B6%88%E6%81%AF
    return {"type": "xml", "data": {"data": data}}


def json(data: str) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#json-%E6%B6%88%E6%81%AF
    return {"type": "json", "data": {"data": data}}


def music(data: str) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E9%9F%B3%E4%B9%90%E5%88%86%E4%BA%AB-
    return {"type": "music", "data": {"type": "qq", "id": data}}

def reply(id: str) -> dict:
    return {"type": "reply", "data": {"type": "reply", "id": id}}

def forward(messages: list):
    res = []
    res.append({
        "type" : "node",
        "data" : {
            "content" : messages
        }
    })
    return res
