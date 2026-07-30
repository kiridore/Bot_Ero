from datetime import datetime
from typing import Tuple

from core.base import Plugin
from core.cq import at, text
from core.utils import register_plugin

from .parser import _format_recur_desc, _next_recurring_fire, _parse_create_body


@register_plugin
class GroupAlarmPlugin(Plugin):
    name = "group_alarm"
    description = "群聊或私聊定时闹钟：/闹钟 …"
    _last_alarm_scan_minute = None

    def match(self, event_type):
        if event_type == "message":
            return self._match_text_command()
        if event_type == "meta":
            return self._should_scan_alarms()
        return False

    def _match_text_command(self):
        if not self.bot_event.message:
            return False
        m0 = self.bot_event.message[0]
        if m0.get("type") != "text":
            return False
        t = m0["data"]["text"].strip()
        if t.startswith("／"):
            t = "/" + t[1:]
        return t.startswith("/闹钟") or t.startswith("/鬧鐘")

    def _should_scan_alarms(self):
        now = datetime.now()
        key = now.strftime("%Y-%m-%d %H:%M")
        if GroupAlarmPlugin._last_alarm_scan_minute == key:
            return False
        GroupAlarmPlugin._last_alarm_scan_minute = key
        return True

    def _command_body(self) -> Tuple[str, str]:
        raw = self.bot_event.message[0]["data"]["text"].strip()
        if raw.startswith("／"):
            raw = "/" + raw[1:]
        if raw.startswith("/鬧鐘"):
            return "/鬧鐘", raw[len("/鬧鐘") :].strip()
        return "/闹钟", raw[len("/闹钟") :].strip()

    def handle(self):
        if self.bot_event.post_type == "meta_event":
            self._handle_meta_due()
            return
        if not self.bot_event.message or self.bot_event.message[0].get("type") != "text":
            return
        _, body = self._command_body()
        if not body:
            self._send_usage()
            return
        first = body.split(None, 1)[0]
        if first in ("一览", "一覽", "清單", "清单"):
            self._handle_list()
            return
        if first in ("取消", "撤銷"):
            rest = body[len(first) :].strip()
            self._handle_cancel(rest)
            return
        self._handle_create(body)

    def _send_usage(self):
        self.api.send_msg(
            text(
                "用法：\n"
                "· 「X年X月X日」无「后」— 具体日历日，可只写年/月/日或任意组合（缺省补当前年、月或 1 日）；"
                "亦可用 YYYY-MM-DD（与「YYYY年MM月DD日」等价）。\n"
                "· 「X年X月X日X时/小时X分/分钟后」— 相对当前时刻的偏移；未写的年/月/日/时/分视为 0；"
                "可与独立 HH:MM 并存，若本段内写了时/分则以本段为准。\n"
                "· 任意闹钟的触发时刻须距当前至少满 5 分钟（不足 5 分钟不可设，刚好 5 分钟可以）。\n"
                "· 循环（须写在开头，且不能与紧接的「…日后」或定时用具体日历日混用）：\n"
                "  「每天」「每日」— 等价于每 1 天；「每N日」或「每N天」— 每隔 N 天；"
                "「每周一」…「每周日」或「每星期一」…「每星期日」；\n"
                "  「每年M月D日」；「每月D日」。\n"
                "· 可同时写 HH:MM；无时间时，具体日/循环为当天当前时刻；"
                "相对「…后」若未写时/分，则为偏移后沿用当前时刻（否则以段内时/分为准）。\n"
                "· /闹钟 HH:MM 内容 — 无日期时，为当天该时刻；若该时刻已过则无法设置。\n"
                "须至少包含上述之一，且必须有文字内容。\n"
                "群聊与私聊均可设置；到点后在原会话中提醒。\n"
                "/闹钟、/鬧鐘 一览／一覽／清單 — 查看本人待触发闹钟\n"
                "/闹钟、/鬧鐘 取消／撤銷 <编号> — 取消对应闹钟（仅本人创建）；"
                "亦可用全形「／」代替「/」。"
            )
        )

    def _handle_list(self):
        gid = self.bot_event.group_id
        uid = self.bot_event.user_id
        rows = self.dbmanager.alarm.pending(uid, gid)
        if not rows:
            self.api.send_msg(text("你还没有待触发的闹钟。"))
            return
        lines = []
        for rid, fat, c, is_rec, rk, ra, rb, rc in rows:
            preview = c if len(c) <= 40 else c[:40] + "…"
            tnext = (fat or "")[:16]
            if int(is_rec or 0) and int(rk or 0) > 0:
                rec = _format_recur_desc(int(rk), int(ra or 0), int(rb or 0), int(rc or 0))
                lines.append("#{} · {} · {} · {}".format(rid, rec, tnext, preview))
            else:
                lines.append("#{} · {} · {}".format(rid, tnext, preview))
        self.api.send_msg(text("待触发闹钟：\n" + "\n".join(lines)))

    def _handle_cancel(self, rest: str):
        if not rest.isdigit():
            self.api.send_msg(text("请使用：/闹钟 取消 <编号> 或 /鬧鐘 撤銷 <编号>（编号见「一览／一覽」）。"))
            return
        aid = int(rest)
        ok = self.dbmanager.alarm.cancel(aid, self.bot_event.user_id, self.bot_event.group_id)
        if ok:
            self.api.send_msg(text("小埃已经取消闹钟 #{}。".format(aid)))
        else:
            self.api.send_msg(text("取消失败：编号不存在、已触发或不是你创建的闹钟。"))

    def _handle_create(self, body: str):
        parsed = _parse_create_body(body)
        if isinstance(parsed, str):
            self.api.send_msg(text(parsed))
            return
        fire, clean_content, recur = parsed
        is_priv = self.bot_event.group_id is None
        aid = self.dbmanager.alarm.add(
            self.bot_event.user_id,
            fire,
            clean_content,
            self.bot_event.group_id,
            is_private=is_priv,
            recur=recur,
        )
        if recur:
            k, a, b, c = recur
            extra = "（{} 循环）".format(_format_recur_desc(k, a, b, c))
        else:
            extra = ""
        self.api.send_msg(
            text(
                "小埃记住了，已设置闹钟 #{}，将于 {} 提醒你{}：「{}」".format(
                    aid, fire.strftime("%Y-%m-%d %H:%M"), extra, clean_content
                )
            )
        )

    def _handle_meta_due(self):
        db = self.dbmanager
        now = datetime.now()
        for row in db.alarm.due(now):
            aid = row[0]
            gid = row[1]
            creator_uid = row[2]
            content = row[3]
            fat = row[4]
            is_priv = int(row[5] or 0)
            is_rec = int(row[6] or 0)
            rk = int(row[7] or 0)
            ra = int(row[8] or 0)
            rb = int(row[9] or 0)
            rc = int(row[10] or 0)
            when_label = (fat or "")[:16]
            line = "预约「{}」的小埃提醒服务来了喵：\x20{}".format(when_label, content)
            if is_rec and rk > 0:
                if is_priv:
                    self.api.call_api(
                        "send_private_msg",
                        {"user_id": int(creator_uid), "message": (text(line),)},
                    )
                else:
                    self.api.call_api(
                        "send_group_msg",
                        {
                            "group_id": int(gid),
                            "message": (at(int(creator_uid)), text("\n"), text(line)),
                        },
                    )
                prev_dt = datetime.strptime(fat, "%Y-%m-%d %H:%M:%S")
                nxt = _next_recurring_fire(prev_dt, now, rk, ra, rb, rc)
                db.alarm.advance(aid, fat, nxt)
            else:
                if not db.alarm.mark_fired(aid):
                    continue
                if is_priv:
                    self.api.call_api(
                        "send_private_msg",
                        {"user_id": int(creator_uid), "message": (text(line),)},
                    )
                else:
                    self.api.call_api(
                        "send_group_msg",
                        {
                            "group_id": int(gid),
                            "message": (at(int(creator_uid)), text("\n"), text(line)),
                        },
                    )