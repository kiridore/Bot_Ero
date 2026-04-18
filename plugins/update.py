import os
import sys
import time
from core import api, context
from core.base import Plugin
from core.cq import text
import git

from core.utils import register_plugin
@register_plugin
class UpdatePlugin(Plugin):
    name = 'update_bot'
    description = '拉取远程更新并重启机器人。'

    def match(self, message_type):
        return self.super_user() and self.on_full_match("/更新")

    def handle(self):
        self.api.send_msg(text("正在检测更新喵~"))
        repo = git.Repo("./")

        old_commit = repo.head.commit.hexsha

        origin = repo.remotes.origin
        origin.pull()

        new_commit = repo.head.commit.hexsha

        if old_commit != new_commit:
            commit_range = f"{old_commit}..{new_commit}"
            commits = list(repo.iter_commits(commit_range))
            self.api.send_msg(text(f"更新了 {len(commits)} 个 补丁，5s后重启了喵~"))
            time.sleep(5)
            # 更新成功并重启
            os.execv(sys.executable, ['python3'] + sys.argv)
        else:
            self.api.send_msg(text("小埃同学已经是最新版本了喵~"))

