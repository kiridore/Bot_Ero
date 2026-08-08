from datetime import datetime, timedelta


def settlement_day_key(checkin_date: str) -> str:
    """与 Bot 结算日一致：打卡时间减 8 小时后取日期。"""
    dt = datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
    dt = dt - timedelta(hours=8)
    return dt.strftime("%Y-%m-%d")


def settlement_day_range(day_key: str) -> tuple[str, str]:
    """结算日对应的打卡时间区间 [start, end]（含端点）。"""
    d = datetime.strptime(day_key, "%Y-%m-%d")
    start = d + timedelta(hours=8)
    end = d + timedelta(days=1, hours=8, seconds=-1)
    return (
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
    )
