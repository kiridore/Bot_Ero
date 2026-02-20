from datetime import datetime, timedelta
import sqlite3

from core import utils

conn = sqlite3.connect("data.db")
cur = conn.cursor()

year = 2025
start_date = f"{year}-01-01 00:00:00"
end_date = f"{year}-12-31 23:59:59"
cur.execute(
    """
    SELECT * FROM checkin_records
    WHERE checkin_date BETWEEN ? AND ?
    ORDER BY checkin_date DESC
    """,
    (start_date, end_date)
)
rows = cur.fetchall()

conn.commit()
conn.close()

user_list = {}
for row in rows:
    user_id = row[1]
    user_list.setdefault(user_id, 0)
    user_list[user_id] += 1

# sort by count
user_list = dict(sorted(user_list.items(), key=lambda item: item[1], reverse=True))
for user_id, count in user_list.items():
    print(f"{user_id}---{count}")

# for row in rows:
#     user_id = row[1]
#     checkin_date = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
#     week_start, week_end = utils.get_monday_to_monday(checkin_date)
#     week_start = week_start.split(" ")[0]
#
#     user_list.setdefault(user_id, [])
#     user_list[user_id].append(week_start)
#
# with open("out.csv", "w") as f:
#     #title
#     date = datetime(year, 1, 1)
#     print("name", end=",", file=f)
#     while date.year == year:
#         week_start, week_end = utils.get_monday_to_monday(date)
#         week_start = week_start.split(" ")[0]
#         print(week_start, end=",", file=f)
#         date = date + timedelta(days = 7)
#
#     print("", end = "\n", file=f)
#     #data
#     for user_id, checkin_list in user_list.items():
#         print(user_id, end = ",", file=f)
#         # 从一月一日开始，循环当年的每一个周一
#
#         date = datetime(year, 1, 1)
#         while date.year == year:
#             week_start, week_end = utils.get_monday_to_monday(date)
#             week_start = week_start.split(" ")[0]
#             if week_start in checkin_list:
#                 print("√", end=",", file=f)
#             else:
#                 print("×", end=",", file=f)
#             date = date + timedelta(days = 7)
#
#         print("", end = "\n", file=f)
#
