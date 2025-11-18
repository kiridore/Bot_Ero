import os
from core.base import Plugin
from core.cq import text

class BackupPlugin(Plugin):
    def match(self):
        return self.on_full_match("/数据备份")

    def handle(self):
        rows = self.dbmanager.get_all_record()
        self.send_msg(text("找到了{}条打卡记录，正在备份到硬盘".format(rows)))
        for row in rows:
            # 根据QQ号创建文件夹
            user_id = row[1]
            user_folder = f"/app/llonebot/tmp/{user_id}"
            os.makedirs(user_folder, exist_ok=True)
            backup_count = 0
            # 检测图片是否已经存在对应的文件夹
            image_path = os.path.join(user_folder, f"{row[3]}.jpg")
            if not os.path.exists(image_path):
                image_file = self.get_image(row[3])
                if image_file != "":
                    with open(image_path, "wb") as f:
                        f.write(image_file) # 保存图片到文件
                        backup_count += 1

            self.send_msg(text("用户{}的打卡记录备份完成，共备份了{}张图片".format(user_id, backup_count)))

