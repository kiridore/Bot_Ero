from typing import override
from core.base import Plugin
from core.cq import text
import core.context as context

import shutil
from datetime import datetime

class MonitorPlugin(Plugin):
    def match(self, message_type):
        return self.super_user() and self.on_full_match("/系统状态")

    def handle(self):
        usage = shutil.disk_usage("/")
        
        total_disk = usage.total / (1024**3)
        used_disk = usage.used / (1024**3)
        free_disk = usage.free / (1024**3)

        used_persent = used_disk / total_disk * 100
        current_time = datetime.now()
        global script_start_time
        runing_time = (current_time - context.script_start_time)
        # 拆分
        days = runing_time.days
        seconds = runing_time.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        display_str = """小埃同学已经运行了:
{}天 {}小时 {}分钟 {}秒
硬盘使用情况
总计:{:.2f}GB
使用:{:.2f}GB({:.2f}%)
剩余:{:.2f}GB({:.2f}%)"""
        self.api.send_msg(text(display_str.format(days, hours, minutes, secs, total_disk, used_disk, used_persent, free_disk, 100-used_persent)))
    

