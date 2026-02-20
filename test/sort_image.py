from ntpath import isfile
import os
from core.database_manager import DbManager

# 获取文件夹中所有文件
def get_all_files(folder_path):
    import os

    all_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root, file)
            all_files.append(full_path)
    return all_files

dbmanager = DbManager()

rows = dbmanager.get_all_record()

user_png_map = {}

for row in rows:
    user_id = row[1]
    png_name:str = row[3]
    png_name = png_name.replace('{', '').replace('}', '').replace('-', '')
    if user_id not in user_png_map:
        user_png_map[user_id] = []

    user_png_map[user_id].append(png_name)

all_png = get_all_files("./backup/")

for user_id, records in user_png_map.items():
    folder_pattern = "./backup/records/{}".format(user_id)
    os.makedirs(folder_pattern, exist_ok=True)
    for png in records:
        record_path = folder_pattern + "/{}".format(png)
        if not os.path.isfile(record_path):
            print(f"can not find file: {record_path}")
        
