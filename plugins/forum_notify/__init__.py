"""议事厅通知与维护：扫描新帖发群消息、过期投票自动关闭并 emit 结束事件。

通过继承 Plugin + 手动分钟去重（避开 TimedHeartbeatPlugin 单时间点 RUN_AT 限制），
由 bot 主程序在 meta 心跳事件中触发（每秒或更频繁）。
"""

from datetime import datetime

from core.base import Plugin
from core.base import BOT_QQ
from core import config as _config
from core.config import WEB_BASE_URL
from core.cq import text
from core.logger import logger
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
        from core import context as runtime_context
        db = self.dbmanager
        # 新帖通知：默认群未启用（或未配置）时不发送、不标记已通知，帖子保留待重新开启
        notify_target_ok = (
            _config.DEFAULT_GROUP_ID is not None
            and runtime_context.effective_for_scope("forum_notify", group_id=_config.DEFAULT_GROUP_ID)
        )
        # 1. 新帖通知
        posts = db.forum.list_unnotified_posts(limit=10)
        if posts and not notify_target_ok:
            logger.info(
                "论坛有 %s 条新帖未通知（默认群未启用 forum_notify），已保留待重新开启",
                len(posts),
            )
        elif posts:
            for pid, ptype, title, _ in posts:
                url = f"{WEB_BASE_URL}/forum/{pid}"
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
                    actor_id=BOT_QQ,  # 系统事件 actor=bot 本体（同 weekly_report/activity），QQ 0 无法解析头像
                    actor_qq=BOT_QQ,
                    title=f"投票「{title}」已结束",
                    target_url=f"/forum/{pid}",
                    dedup_key=f"forum_poll_close:{pid}",
                )
