"""议事厅通知与维护：扫描新帖发群消息、过期投票自动关闭并 emit 结束事件。

通过继承 Plugin + 手动分钟去重（避开 TimedHeartbeatPlugin 单时间点 RUN_AT 限制），
由 bot 主程序在 meta 心跳事件中触发（每秒或更频繁）。
"""

from datetime import datetime

from core.base import Plugin
from core.cq import text
from core.timeline_client import emit_event
from core.utils import register_plugin


@register_plugin
class ForumNotifyPlugin(Plugin):
    name = "forum_notify"
    description = "议事厅新帖群消息通知 + 过期投票自动关闭"
    _last_run_minute = {}

    def match(self, event_type="message"):
        if event_type != "meta":
            return False
        now = datetime.now()
        run_key = now.strftime("%Y-%m-%d %H:%M")
        if self._last_run_minute.get(self.name) == run_key:
            return False
        self._last_run_minute[self.name] = run_key
        return True

    def handle(self):
        db = self.dbmanager
        # 1. 新帖通知
        posts = db.forum.list_unnotified_posts(limit=10)
        if posts:
            for pid, ptype, title, _ in posts:
                url = f"https://littlero.tech/forum/{pid}"
                prefix = {
                    "post": "长文",
                    "announce": "公告",
                    "poll": "投票",
                }.get(ptype, "帖子")
                self.api.send_msg(text(f"📌 议事厅新{prefix}：「{title}」\n{url}"))
                db.forum.mark_notified(pid)

        # 2. 过期投票自动关闭
        expired = db.forum.list_expired_polls()
        if not expired:
            return
        for pid, title in expired:
            closed = db.forum.close_poll(pid)
            if closed:
                emit_event(
                    source="forum",
                    actor_id="0",  # 系统事件
                    actor_qq="0",
                    title=f"投票「{title}」已结束",
                    target_url=f"/forum/{pid}",
                    dedup_key=f"forum_poll_close:{pid}",
                )
