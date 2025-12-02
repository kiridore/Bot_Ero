import os
from core import context
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
            user_folder = f"{context.data_home_path}/record_images/{user_id}"
            os.makedirs(user_folder, exist_ok=True)
            backup_cnt = 0
            error_cnt = 0
            # 检测图片是否已经存在对应的文件夹
            backup_image = os.path.join(user_folder, f"{row[3]}.jpg")
            if not os.path.exists(backup_image):
                qq_origin_image = self.get_image(row[3])
                if qq_origin_image != "":
                    with open(backup_image, "xb") as f: # 创建一个 backup_image 文件
                        f.write(qq_origin_image) # 保存图片到文件
                        backup_cnt += 1
                else:
                    error_cnt += 1

            self.send_msg(text("用户{}的打卡记录备份完成，共备份了{}张图片, 有{}张图片不幸遗失了".format(user_id, backup_cnt, error_cnt)))

