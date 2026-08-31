import os
import subprocess

import core.context as runtime_context
from core.base import Plugin
from core.config import NICKNAME
from core.cq import text
from core.utils import register_plugin

_LAST_UPDATE_HEAD_FILE = os.path.join(runtime_context.python_data_path, "last_update_head.txt")


@register_plugin
class StartupChangelogPlugin(Plugin):
    name = 'startup_changelog'
    description = '启动后发送最近更新日志。'

    def match(self, message_type):
        return message_type == "meta" and not runtime_context.startup_changelog_sent


    def handle(self):
        if runtime_context.startup_changelog_sent:
            return

        msg = f"早上好！{NICKNAME}开机啦"

        self.api.send_msg(text(msg))
        runtime_context.startup_changelog_sent = True
