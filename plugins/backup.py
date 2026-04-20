import os
import time

import core.context as runtime_context
from core import utils
from core.base import TimedHeartbeatPlugin
from core.cq import text

from core.utils import register_plugin
@register_plugin
class BackupPlugin(TimedHeartbeatPlugin):
    name = 'backup_data'
    description = '定时或手动备份打卡图片数据。'

    RUN_AT = "08:00"

    def match(self, message_type):
        return self.should_run_on_heartbeat(message_type) or self.on_full_match_any("/数据备份", "/數據備份")

    def handle(self):
        rows = self.dbmanager.get_all_record()
        self.api.send_msg(text("早上好，昨天的打卡关门啦，开始进行备份~"))
        self.api.send_msg(text("找到了{}条打卡记录，正在备份到硬盘".format(len(rows))))

        exists_cnt = 0
        success_cnt = 0
        error_cnt = 0
        remedy_cnt = 0

        t0 = time.perf_counter()
        for row in rows:
            # 根据QQ号创建文件夹
            user_id = row[1]
            python_user_folder = f"{runtime_context.python_data_path}/record_images/{user_id}"
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

        elapsed = time.perf_counter() - t0
        if elapsed < 60:
            duration_text = f"{elapsed:.2f} 秒"
        else:
            duration_text = f"{int(elapsed // 60)} 分 {elapsed % 60:.2f} 秒"

        total = len(rows)
        if total:
            safe_pct = (exists_cnt + success_cnt + remedy_cnt) / total * 100
        else:
            safe_pct = 0.0

        summary = (
            "备份完成喵\n"
            "────────\n"
            f"本次耗时：{duration_text}\n"
            "────────\n"
            "统计\n"
            f"· 检查记录：{total} 条\n"
            f"· 校验通过（本地已有）：{exists_cnt} 张\n"
            f"· 新下载备份：{success_cnt} 张\n"
            f"· 备份失败：{error_cnt} 张\n"
            f"· 补卡（跳过图片）：{remedy_cnt} 次\n"
            "────────\n"
            f"数据安全覆盖率：{safe_pct:.2f}%"
        )
        self.api.send_msg(text(summary))
