from core.base import SUPER_USER, TimedHeartbeatPlugin
from core.cq import at, text
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
        error_cnt = 0
        for row in rows:
            status = ensure_checkin_image(self.api, row[1], row[3])
            if status not in ("exists", "downloaded", "remedy"):
                error_cnt += 1

        total = len(rows)
        # ponytail: 空记录视为 100%（无失败），避免每天空 @ 超管；有记录时成功率 = 非失败占比
        safe_pct = (total - error_cnt) / total * 100 if total else 100.0

        if safe_pct < 100:
            self.api.send_msg(*[at(uid) for uid in SUPER_USER], text(f"数据校验成功率：{safe_pct:.2f}%"))
        else:
            self.api.send_msg(text(f"数据校验成功率：{safe_pct:.2f}%"))
