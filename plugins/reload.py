import importlib
import sys
from core.base import Plugin
from core.cq import text

class ReloadPlugin(Plugin):
    def match(self):
        return self.on_full_match("/reload")

    def handle(self):
        # 只允许超级用户触发（比如自己）
        if not self.super_user():
            self.send_msg(text("你没有权限执行此操作"))
            return

        reloaded = []
        for name in list(sys.modules.keys()):
            if name.startswith("plugins.") and name != "plugins.reload":
                importlib.reload(sys.modules[name])
                reloaded.append(name)

        self.send_msg(text(f"热更新完成，共重载 {len(reloaded)} 个插件"))
