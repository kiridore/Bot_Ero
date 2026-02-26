from datetime import datetime
import os
import shutil
from core import context, utils
from core.base import Plugin
from core.cq import text
import requests

class BackupPlugin(Plugin):
    def match(self, message_type):
        # 定时任务
        if message_type == "meta":
            # 获取当前时间
            current_time = datetime.now()
            # 仅在早上八点运行
            if current_time.hour == 8 and current_time.minute == 0:
                return True

        return self.on_full_match("/数据备份")

    def handle(self):
        rows = self.dbmanager.get_all_record()
        self.api.send_msg(text("找到了{}条打卡记录，正在备份到硬盘".format(len(rows))))

        exists_cnt = 0
        success_cnt = 0
        error_cnt = 0
        remedy_cnt = 0

        for row in rows:
            # 根据QQ号创建文件夹
            user_id = row[1]
            python_user_folder = f"{context.python_data_path}/record_images/{user_id}"
            image_name = row[3].replace('{', '').replace('}', '').replace('-', '')

            if image_name == "remedy_checkin": 
                remedy_cnt += 1
                continue

            os.makedirs(python_user_folder, exist_ok=True)
            flag = "成功"

            # 检测图片是否已经存在对应的文件夹
            backup_image = os.path.join(python_user_folder, image_name)

            # 确保大小写有一种图片保存下来了
            if not os.path.exists(backup_image.lower()) and not os.path.exists(backup_image):
                qq_origin_image_name = self.api.get_image(row[3])
                if qq_origin_image_name != "":
                    url = self.api.get_image_url(row[3])
                    ok, msg = utils.download_image(url, backup_image)
                    print("download {}".format(backup_image))

                    # qq_origin_image_name = qq_origin_image_name.replace("/root/.config/QQ", context.onebot_qq_volume)
                    # shutil.copy(qq_origin_image_name, python_user_folder)
                    if not ok:
                        print("备份失败{}".format(msg))
                    else:
                        success_cnt += 1
                else:
                    flag = "QQ图片获取失败"
                    print("尝试备份{}, {}".format(backup_image, flag))
                    error_cnt += 1
            else:
                flag = "无需备份"
                exists_cnt += 1

            # print("尝试备份{}, {}".format(backup_image, flag))
        success_percent = (exists_cnt + success_cnt + remedy_cnt)/len(rows) * 100
        self.api.send_msg(text("备份完成喵，共检查{}次打卡记录\n{}张图片通过数据校验\n本次备份{}张图片\n有{}张图片不幸遗失在历史的长河里\n包含{}次补卡记录\n\n{}%的数据确认安全备份了".format(len(rows), exists_cnt, success_cnt, error_cnt, remedy_cnt, success_percent)))
