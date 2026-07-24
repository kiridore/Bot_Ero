from datetime import datetime, timedelta
from typing import TypeVar
import requests
import os

from core import context
from core.api import ApiWrapper
from core.base import Plugin
from core.database_manager import DbManager

PluginType = TypeVar("PluginType", bound=type[Plugin])
# 返回本周一八点到下周一八点
def get_monday_to_monday(date:datetime | None = None):
    if date is None:
        date = datetime.today()
    # 偏移八小时确保在下一周一是不会出错
    date = date - timedelta(hours=8)
    weekday = date.weekday()
    start = date - timedelta(days=weekday)
    end = start + timedelta(days=7)
    return start.strftime("%Y-%m-%d 08:00:00"), end.strftime("%Y-%m-%d 08:00:00")

def day_of_year(date_str):
    """
    输入格式为 'YYYY-MM-DD HH:MM:SS' 的时间字符串，返回这一年的第几天
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")  # 转为 datetime 对象
    dt = dt - timedelta(hours=8) # 向前偏移八小时，让热度图信息与实际打卡结算日一致
    return dt.timetuple().tm_yday  # 获取一年中的第几天

def add_user_point(db:DbManager, user_id:int, offer:int):
        point = db.get_user_point(user_id)
        db.set_user_point(user_id, point + offer)

def get_image_from_backup(user_id, image):
    python_user_folder = f"{context.python_data_path}/record_images/{user_id}/"
    image_name = image.replace('{', '').replace('}', '').replace('-', '')
    backup_image = os.path.join(python_user_folder, image_name)

    if os.path.exists(backup_image.lower()) or os.path.exists(backup_image):
        return backup_image
    else:
        return ""

def get_image(context, image):
    image_path = get_image_from_backup(context['user_id'], image) 
    if image_path == "":
        image_path = ApiWrapper(context).get_image(image)
    return image_path

def download_image(url, local_path, expected_size=None):
    try:
        proxies = {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890"
        }

        response = requests.get(url, proxies=proxies, timeout=30)
        if response.status_code != 200:
            return False, "HTTP状态码异常"

        if not response.content:
            return False, "内容为空"

        if expected_size:
            if len(response.content) != expected_size:
                return False, "文件大小不匹配"

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(response.content)

        if expected_size:
            if os.path.getsize(local_path) != expected_size:
                return False, "写入后大小异常"

        return True, "下载成功"

    except Exception as e:
        return False, str(e)

def register_plugin(cls: PluginType) -> PluginType:
    if not issubclass(cls, Plugin):
        raise TypeError(f"{cls.__name__} must inherit from Plugin")
    if cls not in context.plugin_registry:
        context.plugin_registry.append(cls)
    return cls

# ponytail: quest defs hardcoded, add admin-created quests later if needed
QUEST_DEFS = [
    {"id": 1, "name": "打个卡先", "trigger": "checkin", "goal": 1, "reward": 1},
    {"id": 2, "name": "三连打卡", "trigger": "checkin", "goal": 3, "reward": 2},
    {"id": 3, "name": "一周都打了", "trigger": "checkin", "goal": 7, "reward": 3},
    {"id": 4, "name": "随便抽抽", "trigger": "lottery", "goal": 3, "reward": 1},
    {"id": 5, "name": "猛猛上瘾", "trigger": "lottery", "goal": 7, "reward": 2},
]

def get_quest_week_key():
    return get_monday_to_monday()[0].split(" ")[0]

def on_quest_trigger(db, user_id, trigger_type):
    week_key = get_quest_week_key()
    if trigger_type == "checkin":
        start, end = get_monday_to_monday()
        count = db.get_distinct_checkin_day_count(user_id, start, end)
    else:
        start, _ = get_monday_to_monday()
        count = db.get_weekly_lottery_draw_count(user_id, start)
    completed = []
    for q in QUEST_DEFS:
        if q["trigger"] != trigger_type:
            continue
        db.upsert_quest_progress(user_id, q["id"], week_key, count)
        if count >= q["goal"] and db.claim_quest_reward(user_id, q["id"], week_key):
            add_user_point(db, user_id, q["reward"])
            db.increment_quest_completion(user_id)
            completed.append({"name": q["name"], "reward": q["reward"]})
    return completed

def on_quest_rollback(db, user_id, trigger_type):
    week_key = get_quest_week_key()
    start, end = get_monday_to_monday()
    count = db.get_distinct_checkin_day_count(user_id, start, end)
    for q in QUEST_DEFS:
        if q["trigger"] != trigger_type:
            continue
        db.upsert_quest_progress(user_id, q["id"], week_key, count)
        if count < q["goal"] and db.revoke_quest_reward(user_id, q["id"], week_key):
            add_user_point(db, user_id, -q["reward"])
