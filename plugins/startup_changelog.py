import subprocess

import core.context as runtime_context
from core.base import Plugin
from core.cq import text


class StartupChangelogPlugin(Plugin):
    name = 'startup_changelog'
    description = '启动后发送最近更新日志。'

    def match(self, message_type):
        return message_type == "meta" and not runtime_context.startup_changelog_sent

    def _get_recent_changelog(self, limit=5):
        try:
            output = subprocess.check_output(
                ["git", "log", f"-{limit}", "--pretty=format:%h %s"],
                stderr=subprocess.STDOUT,
                text=True,
            )
            rows = [line.strip() for line in output.splitlines() if line.strip()]
            if len(rows) == 0:
                return ["暂无更新记录"]
            return rows
        except Exception:
            return ["更新日志读取失败（git log 不可用）"]

    def handle(self):
        if runtime_context.startup_changelog_sent:
            return

        default_group_id = self.context.get("default_group_id")
        if not default_group_id:
            return

        lines = self._get_recent_changelog(limit=5)
        msg = "早上好！小埃同学开机啦，最近更新如下：\n" + "\n".join([f"- {line}" for line in lines])

        # meta 事件不带 group_id，这里显式指定默认群
        self.context["group_id"] = default_group_id
        self.api.send_msg(text(msg))
        runtime_context.startup_changelog_sent = True
