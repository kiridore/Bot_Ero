from datetime import datetime, timedelta

from core.database_manager import DbManager
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

def add_user_point(db:DbManager, user_id:str, offer:int):
        point = db.get_user_point(user_id)
        db.set_user_point(user_id, point + offer)
