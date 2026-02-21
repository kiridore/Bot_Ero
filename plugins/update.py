import os
import sys
from core import context
from core.base import Plugin
from core.cq import text
import git

class UpdatePlugin(Plugin):
    def match(self):
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
            self.api.send_msg(text(f"更新了 {len(commits)} 个 补丁，准备重启了喵~"))
            # 更新成功并重启
            context.should_shutdown = True
            os.execv(sys.executable, ['python3'] + sys.argv)
        else:
            self.api.send_msg(text("小埃同学已经是最新版本了喵~"))

