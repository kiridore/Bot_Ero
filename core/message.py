# MessageEvent消息段中message字段解包
from enum import Enum


class MessageUnit:
    class MessageType(Enum):
        TEXT = 0
        IMAGE = 1
        # VIDEO = 2
        # RECORED = 3 # 语音
        # FILE = 4
        AT = 5
        REPLY = 6 # 回复
        OTHER = -1  # 不处理内容

    def __init__(self, data: dict) -> None:
        if data["type"] == "text":
            self.type = self.MessageType.TEXT
            self.text = data["data"]["text"]

        elif data["type"] == "image":
            self.type = self.MessageType.IMAGE
            self.file = data["data"]["file"]
            self.url = data["data"]["url"]
            self.file_size = data["data"]["file_size"]
            self.summary = data["data"]["summary"]
            self.sub_type = data["data"]["subType"]
            self.thumb = data["data"]["thumb"]
            self.image_type = data["data"]["type"]
            self.name = data["data"]["name"]

        elif data["type"] == "at":
            self.type = self.MessageType.AT
            self.qq = data["data"]["qq"]
            self.name = data["data"]["name"]
            
        elif data["type"] == "reply":
            self.type = self.MessageType.REPLY
            self.id = data["data"]["id"]

        else:
            self.type = self.MessageType.OTHER
