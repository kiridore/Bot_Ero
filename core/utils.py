from datetime import datetime, timedelta

def get_week_start_end(date=None):
    if date is None:
        date = datetime.today()
    weekday = date.weekday()
    start = date - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
