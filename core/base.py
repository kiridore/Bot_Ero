import re
import sqlite3
import json
import queue
import collections
from datetime import datetime
from core.logger import logger

import websocket

from cq import *


WS_APP : websocket.WebSocketApp
only_to_me_flag = False

NICKNAME = ["小埃同学", "bot"]         # 机器人昵称
SUPER_USER = [1057613133]   # 主人的 QQ 号

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

class Plugin:
    def __init__(self, context: dict):
        self.ws = WS_APP
        self.context = context
        self.database_init()

    def __del__(self):
        self.close()

    def database_init(self):
        self.conn = sqlite3.connect("data.db")
        self.cur = self.conn.cursor()
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS checkin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            checkin_date TEXT NOT NULL,
            content TEXT NOT NULL
        );
        """)
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def insert_checkin(self, user_id, images):
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for img in images:
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
                (user_id, today_str, img)
            )
        self.conn.commit()

    def search_checkin_all(self, user_id, limit=9999):
        self.cur.execute(
            """
            SELECT * FROM checkin_records
            WHERE user_id = ?
            ORDER BY checkin_date DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = self.cur.fetchall()
        logger.debug(f"用户{user_id}打卡记录查询结束：")
        for row in rows:
            logger.debug(row)
        return rows

    def search_all_user_checkin_range(self, start_date, end_date, limit=9999):
        self.cur.execute("""
        SELECT * FROM checkin_records
        WHERE checkin_date BETWEEN ? AND ?
        ORDER BY checkin_date DESC
        LIMIT ?
        """, (start_date, end_date, limit))
        rows = self.cur.fetchall()
        return rows

    def search_target_user_checkin_range(self, user_id, start_date, end_date, limit=9999):
        self.cur.execute("""
        SELECT * FROM checkin_records
        WHERE user_id = ?
        AND checkin_date BETWEEN ? AND ?
        ORDER BY checkin_date DESC
        LIMIT ?
        """, (user_id, start_date, end_date, limit))
        rows = self.cur.fetchall()
        return rows

    def delete_checkin_by_id(self, target_id):
        self.cur.execute("""
            DELETE FROM checkin_records
            WHERE id = ?
        """, (target_id, ))
        self.conn.commit()


    def match(self) -> bool:
        return self.on_full_match("hello")

    def handle(self):
        self.send_msg(text("hello world!"))

    def on_message(self) -> bool:
        return self.context["post_type"] == "message"

    def on_full_match(self, keyword="") -> bool:
        return self.on_message() and self.context["message"] == keyword

    def on_begin_with(self, keyword="") -> bool:
        return self.on_message() and self.context["message"].lstrip().startswith(keyword)

    def on_reg_match(self, pattern="") -> bool:
        return self.on_message() and re.search(pattern, self.context["message"])

    def only_to_me(self) -> bool:
        global only_to_me_flag
        if only_to_me_flag:
            return True
        for nick in NICKNAME:
            at_string = f"[CQ:at,qq={self.context['self_id']},name={nick}] "
            if self.on_message() and at_string in self.context["message"]:
                only_to_me_flag = True
                self.context["message"] = self.context["message"].replace(at_string, "")
        return only_to_me_flag

    def super_user(self) -> bool:
        return self.context["user_id"] in SUPER_USER

    def admin_user(self) -> bool:
        return self.super_user() or self.context["sender"]["role"] in ("admin", "owner")

    def call_api(self, action: str, params: dict) -> dict:
        echo_num, q = echo.get()
        data = json.dumps({"action": action, "params": params, "echo": echo_num})
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
        return ret["data"]["file"]

    def get_qq_avatar(self, user_id):
        params = {"user_id": user_id}
        ret = self.call_api("get_qq_avatar", params)
        return ret["data"]["url"]
