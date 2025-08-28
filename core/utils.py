from datetime import datetime, timedelta
# 返回本周一八点到下周一八点
def get_monday_to_monday(date = None):
    if date is None:
        date = datetime.today()
    weekday = date.weekday()
    start = date - timedelta(days=weekday)
    end = start + timedelta(days=7)
    return start.strftime("%Y-%m-%d 08:00:00"), end.strftime("%Y-%m-%d 08:00:00")

def get_week_start_end(date=None):
    if date is None:
        date = datetime.today()
    weekday = date.weekday()
    start = date - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 23:59:59")

def day_of_year(date_str):
    """
    输入格式为 'YYYY-MM-DD HH:MM:SS' 的时间字符串，返回这一年的第几天
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")  # 转为 datetime 对象
    return dt.timetuple().tm_yday  # 获取一年中的第几天
