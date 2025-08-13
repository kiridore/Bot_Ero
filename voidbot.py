import re
import time
import queue
import logging
import threading
import collections
import json as json_
import sqlite3
from datetime import datetime, timedelta
from tracemalloc import start

import websocket

WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址
NICKNAME = ["小埃同学", "bot"]         # 机器人昵称
SUPER_USER = [1057613133]   # 主人的 QQ 号
# 日志设置  level=logging.DEBUG -> 日志级别为 DEBUG
logging.basicConfig(level=logging.DEBUG, format="[void] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

only_to_me_flag = False

def get_week_start_end(date=None):
    if date is None:
        date = datetime.today()
    # 当前是星期几，周一是0，周日是6
    weekday = date.weekday()
    # 计算本周周一日期
    start = date - timedelta(days=weekday)
    # 本周周日日期
    end = start + timedelta(days=6)
    # 返回日期（年月日）
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

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
        data = json_.dumps({"action": action, "params": params, "echo": echo_num})
        logger.info("发送调用 <- " + data)
        self.ws.send(data)
        try:    # 阻塞至响应或者等待30s超时
            return q.get(timeout=30)
        except queue.Empty:
            logger.error("API调用[{echo_num}] 超时......")

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



def text(string: str) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E7%BA%AF%E6%96%87%E6%9C%AC
    return {"type": "text", "data": {"text": string}}


def image(file: str, cache=True) -> dict:
    # https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#%E5%9B%BE%E7%89%87
    return {"type": "image", "data": {"file": file, "cache": cache}}


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


"""
在下面加入你自定义的插件，自动加载本文件所有的 Plugin 的子类
只需要写一个 Plugin 的子类，重写 match() 和 handle()
match() 返回 True 则自动回调 handle()
"""


# class TestPlugin(Plugin):
#     def match(self):  # 说 hello 则回复
#         return self.on_full_match("hello")
#
#     def handle(self):
#         self.send_msg(at(self.context["user_id"]), text("hello world!"))

class MenuPlugin(Plugin):
    def match(self):
        return self.only_to_me() and self.on_full_match("菜单")

    def handle(self):
        self.send_msg(text("""
小埃同学现在还只有打卡功能喵
---------------------------
/打卡 加上你的图就可以完成打卡了喵
/本周打卡图 统计本周上传的打卡图，通过小窗发送
/个人打卡记录 统计有史以来所有的打卡次数
/本周板油 统计本周有那些板油完成了打卡
/撤回打卡 撤回本周最近一次打卡
            """))


# 打卡插件
class CheckinPlugin(Plugin):
    def match(self):
        return self.on_begin_with("/打卡")

    def handle(self):
        img_list = self.extract_images(self.context["message"])
        if len(img_list) <= 0:
            self.send_msg(text("没有图片是没办法打卡的喵"))
        else:
            for img_name in img_list :
                # 找到的图片列表
                logger.debug("{}".format(self.get_image(img_name)))
            start_date, end_date = get_week_start_end()

            #先打卡后搜索
            self.insert_checkin(self.context["user_id"], img_list)
            checkin_list = self.search_target_user_checkin_range(self.context["user_id"], start_date + " 00:00:00", end_date + " 23:59:59")
            self.send_msg(at(self.context["user_id"]), text(" 打卡成功喵\n收录了{}张图片\n完成本周第{}次打卡喵".format(len(img_list), len(checkin_list))))

    def extract_images(self, text: str):
        # 用非贪婪匹配 .*? 避免跨多个中括号匹配
        pattern = r'\[CQ:image,file=([^,\]]+)'
        return re.findall(pattern, text)


class DisplayWeekCheckinImage(Plugin):
    def match(self):
        return self.on_full_match("/本周打卡图")

    def handle(self):
        start_date, end_date = get_week_start_end()
        rows = self.search_target_user_checkin_range(self.context["user_id"], start_date + " 00:00:00", end_date + " 23:59:59")
        time_map = {}
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
        
        self.send_msg(at(self.context["user_id"]), text("\n本周一共打了{}次卡\n收录了{}张图".format(len(time_map), len(rows))))
        for row in rows:
            image_file = self.get_image(row[3])
            self.send_private_msg(image(image_file))

class SearchCheckinPlugin(Plugin):
    def match(self):
        return self.on_full_match("/个人打卡记录")

    def handle(self):
        rows = self.search_checkin_all(self.context["user_id"])
        time_map = {}
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
        display_str = " 累计共打卡{}次\n收录了{}张打卡图:\n".format(len(time_map), len(rows))
        for time_stamp, count in time_map.items():
            time_format_str = "{} {}张图\n".format(time_stamp, count)
            display_str += time_format_str

        self.send_msg(at(self.context["user_id"]), text(display_str))

# 每周打卡板油
class WeekCheckinListPlugin(Plugin):
    def match(self):
        return self.on_full_match("/本周板油")

    def handle(self):
        #计算本周起止日期
        start_date, end_date = get_week_start_end()
        checkin_users = self.search_all_user_checkin_range(start_date + " 00:00:00", end_date + " 23:59:59")
        if len(checkin_users) <= 0:
            self.send_msg(text("本周({}-{})竟然还没有板油完成打卡".format(start_date, end_date)))
        else:
            display_str = ""
            user_map = {}
            logger.debug(checkin_users)
            #[(1, 1057613133, '2025-08-12 01:22:56', 'EDE6A7B4C56C0F2180D1C54AF7877B0C.png')]
            for user_info in checkin_users:
                user_map[user_info[1]] = user_info[2]

            for user_id, checkin_time in user_map.items():
                group_member_info = self.get_group_member_info(user_id)
                display_row = "{}, {}\n".format(group_member_info["card"], checkin_time)
                display_str += display_row
            self.send_msg(text("{}-{}\n共有{}名板油完成了打卡:\n{}".format(start_date, end_date, len(user_map), display_str)))

class RollbackCheckinPlugin(Plugin):
    def match(self):
        return self.on_full_match("/撤回打卡")

    def handle(self):
        start_date, end_date = get_week_start_end()
        rows = self.search_target_user_checkin_range(self.context["user_id"], start_date + " 00:00:00", end_date + " 23:59:59")
        if len(rows) <= 0:
            self.send_msg(text("本周你还没打过卡呢！"))
        else:
            del_image = self.get_image(rows[0][3])
            del_time = rows[0][2]
            logger.debug(rows)
            self.send_msg(text("成功撤回了本周最近一次打卡喵:\n{}".format(del_time)), image(del_image))
            self.delete_checkin_by_id(rows[0][0])




"""
在上面自定义你的插件
"""


def plugin_pool(context: dict):
    # 遍历所有的 Plugin 的子类，执行匹配
    for P in Plugin.__subclasses__():
        plugin = P(context)
        if plugin.match():
            plugin.handle()

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


def on_message(_, message):
    # https://github.com/botuniverse/onebot-11/blob/master/event/README.md
    context = json_.loads(message)
    if "echo" in context:
        logger.debug("调用返回 -> " + message)
        # 响应报文通过队列传递给调用 API 的函数
        echo.match(context)
    elif "meta_event_type" in context:
        logger.debug("心跳事件 -> " + message)
    else:
        logger.info("收到事件 -> " + message)
        # 消息事件，开启线程
        global only_to_me_flag
        only_to_me_flag = False
        t = threading.Thread(target=plugin_pool, args=(context, ))
        t.start()


if __name__ == "__main__":
    echo = Echo()
    WS_APP = websocket.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_open=lambda _: logger.debug("连接成功......"),
        on_close=lambda _: logger.debug("重连中......"),
    )

    while True:  # 掉线重连
        # 数据储存
        logger.info("数据库启动")

        WS_APP.run_forever()

        time.sleep(5)

