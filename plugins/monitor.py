import shutil
from datetime import datetime

import core.context as context
from core.base import Plugin
from core.cq import text
from core.utils import register_plugin


def _progress_bar(percent: float, width: int = 16) -> str:
    pct = max(0.0, min(100.0, float(percent)))
    filled = min(int(width * pct / 100.0), width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct:.1f}%"


@register_plugin
class MonitorPlugin(Plugin):
    name = 'show_system_status'
    description = '查询机器人运行时长、磁盘、内存与 CPU 状态。'

    def match(self, message_type):
        return self.super_user() and self.on_full_match_any("/系统状态", "/系統狀態")

    def handle(self):
        usage = shutil.disk_usage("/")
        total_disk = usage.total / (1024**3)
        used_disk = usage.used / (1024**3)
        free_disk = usage.free / (1024**3)
        used_percent = used_disk / total_disk * 100

        now = datetime.now()
        running = now - context.script_start_time
        days = running.days
        sec = running.seconds
        hours = sec // 3600
        minutes = (sec % 3600) // 60
        secs = sec % 60

        lines = [
            "小埃同学已经运行了:",
            f"{days}天 {hours}小时 {minutes}分钟 {secs}秒",
            "",
            "磁盘",
            _progress_bar(used_percent),
            f"总计:{total_disk:.2f}GB | 已用:{used_disk:.2f}GB | 剩余:{free_disk:.2f}GB",
        ]

        try:
            import psutil

            vm = psutil.virtual_memory()
            mem_percent = vm.percent
            mem_used_gb = vm.used / (1024**3)
            mem_total_gb = vm.total / (1024**3)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            lines.extend(
                [
                    "",
                    "内存",
                    _progress_bar(mem_percent),
                    f"已用:{mem_used_gb:.2f}GB / 总计:{mem_total_gb:.2f}GB",
                    "",
                    "CPU",
                    _progress_bar(cpu_percent),
                ]
            )
        except ImportError:
            lines.extend(["", "内存/CPU: 请 pip install psutil 后重试"])

        self.api.send_msg(text("\n".join(lines)))
