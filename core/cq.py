import core.base

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

def forward(messages: list):
    return {
        "type" : "node",
        "data" : {
            "content" : [
                {
                    "type": "text",
                    "data": {
                        "text": "hahahaha"
                    }
                }
            ]
        }
    }
