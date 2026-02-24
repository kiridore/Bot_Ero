import json as json_
import queue
import websocket
import collections

from core.logger import logger
from core.database_manager import DbManager
from core.cq import *

class Echo:
    def __init__(self):
        self.echo_num = 0
        self.echo_list = collections.deque(maxlen=20)

    def get(self):
        self.echo_num += 1
        q = queue.Queue(maxsize=1)
        self.echo_list.append((self.echo_num, q))
        return self.echo_num, q

    def match(self, context: dict):
        for obj in self.echo_list:
            if context["echo"] == obj[0]:
                obj[1].put(context)

echo : Echo
WS_APP : websocket.WebSocketApp

class ApiWrapper:
    def __init__(self, context: dict):
        self.ws = WS_APP
        self.context = context
        self.dbmanager = DbManager()

    def call_api(self, action: str, params: dict) -> dict:
        echo_num, q = echo.get()
        data = json_.dumps({"action": action, "params": params, "echo": echo_num})
        logger.info("发送调用 <- " + data)
        self.ws.send(data)
        try:    # 阻塞至响应或者等待30s超时
            return q.get(timeout=30)
        except queue.Empty:
            logger.error("API调用[{echo_num}] 超时......")
            return {}

    def send_msg(self, *message) -> int:
        # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#send_msg-%E5%8F%91%E9%80%81%E6%B6%88%E6%81%AF
        if "group_id" in self.context and self.context["group_id"]:
            return self.send_group_msg(*message)
        else:
            return self.send_private_msg(*message)

    def send_private_msg(self, *message) -> int:
        # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#send_private_msg-%E5%8F%91%E9%80%81%E7%A7%81%E8%81%8A%E6%B6%88%E6%81%AF
        params = {"user_id": self.context["user_id"], "message": message}
        ret = self.call_api("send_private_msg", params)
        return 0 if ret is None or ret["status"] == "failed" else ret["data"]["message_id"]

    def send_group_msg(self, *message) -> int:
        # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#send_group_msg-%E5%8F%91%E9%80%81%E7%BE%A4%E6%B6%88%E6%81%AF
        params = {"group_id": self.context["group_id"], "message": message}
        ret = self.call_api("send_group_msg", params)
        return 0 if ret is None or ret["status"] == "failed" else ret["data"]["message_id"]

    def get_group_member_info(self, user_id):
        #https://github.com/botuniverse/onebot-11/blob/master/api/public.md#get_group_member_info-%E8%8E%B7%E5%8F%96%E7%BE%A4%E6%88%90%E5%91%98%E4%BF%A1%E6%81%AF
        params = {"group_id": self.context["group_id"], "user_id": user_id}
        ret = self.call_api("get_group_member_info", params)
        return ret["data"]

    def get_image(self, file):
        # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#get_image-%E8%8E%B7%E5%8F%96%E5%9B%BE%E7%89%87
        params = {"file": file}
        ret = self.call_api("get_image", params)
        if ret["status"] == "ok":
            return ret["data"]["file"]
        else :
            return ""

    def get_qq_avatar(self, user_id):
        params = {"user_id": user_id}
        ret = self.call_api("get_qq_avatar", params)
        return ret["data"]["url"]

    def set_friend_add_request(self, flag, approve = True):
        params = {"flag": flag, "approve" : approve, "remark": ""}
        self.call_api("set_friend_add_request", params)

    def send_forward_msg(self, message: list):
        if "group_id" in self.context and self.context["group_id"]:
            return self.send_group_forward_msg(message)
        else:
            return self.send_private_forward_msg(message)

    def send_group_forward_msg(self, message: list):
        params = {"group_id": self.context["group_id"], "messages": forward(message)}
        ret = self.call_api("send_group_forward_msg", params)
        return 0 if ret is None or ret["status"] == "failed" else 1

    def send_private_forward_msg(self, message: list):
        params = {"user_id": self.context["user_id"], "messages": forward(message)}
        ret = self.call_api("send_private_forward_msg", params)
        return 0 if ret is None or ret["status"] == "failed" else 1

    def get_group_album_list(self, group_id):
        params = {"group_id": group_id}
        ret = self.call_api("get_group_album_list", params)
        return ret["data"]

    def set_group_special_title(self, group_id, user_id, title):
        params = {"group_id": group_id, "user_id": user_id, "sepcial_title": title}
        ret = self.call_api("set_group_special_title", params)
        return 0
    pass
