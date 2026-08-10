import time

from core.base import TimedHeartbeatPlugin
from core.cq import text

from core.utils import register_plugin, ensure_checkin_image
@register_plugin
class BackupPlugin(TimedHeartbeatPlugin):
    name = 'backup_data'
    description = '定时或手动备份打卡图片数据。'

    RUN_AT = "08:00"

    def match(self, message_type):
        return self.should_run_on_heartbeat(message_type) or self.on_full_match_any("/数据备份", "/數據備份")

    def handle(self):
        rows = self.dbmanager.checkin.all_records()
        self.api.send_msg(text("早上好，昨天的打卡关门啦，开始进行备份~"))
        self.api.send_msg(text("找到了{}条打卡记录，正在备份到硬盘".format(len(rows))))

        exists_cnt = 0
        success_cnt = 0
        error_cnt = 0
        remedy_cnt = 0

        t0 = time.perf_counter()
        for row in rows:
            user_id = row[1]
            status = ensure_checkin_image(self.api, user_id, row[3])

            if status == "remedy":
                remedy_cnt += 1
            elif status == "exists":
                exists_cnt += 1
            elif status == "downloaded":
                success_cnt += 1
            else:
                error_cnt += 1

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
