import os
import sys
from core import context
from core.base import Plugin
from core.cq import text

class RestartPlugin(Plugin):
    def match(self):
        return self.super_user() and self.on_full_match("/重启")

    def handle(self):
        self.send_msg(text("小埃同学要关机了喵"))
        context.should_shutdown = True
        os.execv(sys.executable, ['python'] + sys.argv)
