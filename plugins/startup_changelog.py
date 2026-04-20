import os
import subprocess

import core.context as runtime_context
from core.base import Plugin
from core.cq import text
from core.utils import register_plugin

_LAST_UPDATE_HEAD_FILE = os.path.join(runtime_context.python_data_path, "last_update_head.txt")


@register_plugin
class StartupChangelogPlugin(Plugin):
    name = 'startup_changelog'
    description = '启动后发送最近更新日志。'

    def match(self, message_type):
        return message_type == "meta" and not runtime_context.startup_changelog_sent

    def _read_last_update_head(self):
        try:
            with open(_LAST_UPDATE_HEAD_FILE, encoding="utf-8") as f:
                line = f.readline().strip()
                return line or None
        except OSError:
            return None

    def _commit_hashes_since(self, baseline: str):
        try:
            out = subprocess.check_output(
                ["git", "rev-list", f"{baseline}..HEAD"],
                stderr=subprocess.STDOUT,
                text=True,
            )
            return {h.strip() for h in out.splitlines() if h.strip()}
        except Exception:
            return set()

    def _get_recent_changelog(self, limit=5):
        try:
            output = subprocess.check_output(
                ["git", "log", f"-{limit}", "--pretty=format:%H%x09%s"],
                stderr=subprocess.STDOUT,
                text=True,
            )
            raw_rows = [line.strip() for line in output.splitlines() if line.strip()]
            if len(raw_rows) == 0:
                return ["暂无更新记录"]

            baseline = self._read_last_update_head()
            new_hashes = self._commit_hashes_since(baseline) if baseline else set()

            rows = []
            for line in raw_rows:
                if "\t" not in line:
                    continue
                h, subject = line.split("\t", 1)
                h = h.strip()
                subject = subject.strip()
                if baseline and h in new_hashes:
                    rows.append(f"(new) {subject}")
                else:
                    rows.append(subject)
            return rows if rows else ["暂无更新记录"]
        except Exception:
            return ["更新日志读取失败（git log 不可用）"]

    def handle(self):
        if runtime_context.startup_changelog_sent:
            return

        lines = self._get_recent_changelog(limit=5)
        msg = "早上好！小埃同学开机啦，最近更新如下：\n" + "\n".join([f"- {line}" for line in lines]) + "\n 本次共启用了 {} 个插件".format(runtime_context.plugin_registry.__len__())

        self.api.send_msg(text(msg))
        runtime_context.startup_changelog_sent = True
