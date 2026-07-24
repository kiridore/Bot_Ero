from core.base import Plugin, TimedHeartbeatPlugin
from core.cq import text
from core.utils import register_plugin, get_monday_to_monday, get_quest_week_key, QUEST_DEFS


@register_plugin
class WeeklyQuestPlugin(Plugin):
    name = 'weekly_quest'
    description = '查看本周任务进度'

    def match(self, message_type):
        return self.on_full_match("/周常")

    def handle(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return

        start_date, end_date = get_monday_to_monday()
        week_start_short = start_date.split(" ")[0][5:]
        week_end_short = end_date.split(" ")[0][5:]
        week_key = get_quest_week_key()

        progress = self.dbmanager.get_quest_progress(user_id, week_key)

        lines = [f"📋 本周任务 ({week_start_short} - {week_end_short})"]
        lines.append("━" * 22)

        for q in QUEST_DEFS:
            p = progress.get(q["id"], {})
            cur = p.get("progress", 0)
            done = p.get("completed", 0)
            mark = "✅" if done else "  "
            bar = _make_bar(cur, q["goal"])
            status = "已完成" if done else "进行中"
            lines.append(f"{mark} {q['name']:6s}  [{cur}/{q['goal']}]  +{q['reward']}  {bar}  {status}")

        self.api.send_msg(text("\n".join(lines)))


def _make_bar(cur, goal, width=12):
    # ponytail: simple proportional bar, no Unicode tricks
    filled = round(cur / goal * width) if goal > 0 else 0
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


@register_plugin
class WeeklyQuestResetPlugin(TimedHeartbeatPlugin):
    name = 'weekly_quest_reset'
    description = '每周一08:00清理过期任务进度'
    RUN_AT = "08:00"
    RUN_WEEKDAYS = [1]

    def handle(self):
        self.dbmanager.cleanup_old_quest_progress(get_quest_week_key())
