import os
import shutil
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
            image_name = row[3].replace('{', '').replace('}', '').replace('-', '')
            os.makedirs(user_folder, exist_ok=True)
            flag = "成功"
            # 检测图片是否已经存在对应的文件夹
            backup_image = os.path.join(user_folder, image_name)
            if not os.path.exists(backup_image):
                qq_origin_image = self.get_image(row[3])
                if qq_origin_image != "":
                    qq_origin_image = qq_origin_image
                    # shutil.copy(qq_origin_image, user_folder)
                else:
                    flag = "QQ图片获取失败"
            else:
                flag = "无需备份"

            print("尝试备份{}, {}".format(backup_image, flag))
        self.send_msg(text("备份完成，详情查看日志文件"))

