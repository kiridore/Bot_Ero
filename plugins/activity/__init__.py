import json
import os
from datetime import datetime

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from .logic import build_ring, relay_assignments, current_turn
from . import archive as archive_mod


def _parse_deadline(raw: str) -> str | None:
    """接受 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD HH:MM:SS'，返回完整格式；非法返回 None。"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 模块级辅助（插件类共用，Task 5 完整实现） ──

def _send_private(api, user_id: int, *message):
    api.call_api("send_private_msg", {"user_id": int(user_id), "message": list(message)})


def _announce_group(api, group_id: int, text_body: str):
    api.call_api("send_group_msg", {"group_id": int(group_id), "message": [text(text_body)]})


@register_plugin
class ActivityPlugin(Plugin):
    name = "activity"
    description = "群活动：接龙与匹配下家"

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _sender_nickname(self) -> str:
        sender = self.bot_event.sender
        if sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or f"用户{self.bot_event.user_id}"
        return f"用户{self.bot_event.user_id}"

    def _send_private(self, user_id: int, *message):
        _send_private(self.api, user_id, *message)

    def _announce_group(self, group_id: int, text_body: str):
        _announce_group(self.api, group_id, text_body)

    def match(self, event_type="message") -> bool:
        if event_type != "message":
            return False
        body = self._first_text()
        if not body:
            return False
        parts = body.split()
        if parts[0] == "/活动" and self.bot_event.group_id is not None:
            return True
        if parts[0] == "/提交" and self.bot_event.is_private:
            return True
        return False

    def handle(self):
        try:
            parts = self._first_text().split()
            if parts[0] == "/活动":
                self._route_group_command(parts[1:])
            else:
                self._handle_submit(parts[1:])
        except Exception:
            logger.exception("Activity 处理异常")

    # ── 群聊指令路由 ──────────────────────────────────

    def _route_group_command(self, args: list[str]):
        gid = self.bot_event.group_id
        uid = str(self.bot_event.user_id)
        if not args:
            self._show_usage()
            return
        sub = args[0]
        if sub == "创建":
            self._handle_create(args[1:])
        elif sub == "加入":
            self._handle_join(gid, uid)
        elif sub == "退出":
            self._handle_leave(gid, uid)
        elif sub == "开始":
            self._handle_start(gid, uid)
        elif sub == "状态":
            self._handle_status(gid)
        elif sub == "结束":
            self._handle_end(gid, uid)
        else:
            self._show_usage()

    def _show_usage(self):
        self.api.send_msg(text(
            "活动指令：\n"
            "/活动 创建 接龙 <标题> [每人小时数]\n"
            "/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>\n"
            "/活动 加入 / 退出\n"
            "/活动 开始（创建人）\n"
            "/活动 状态 / 结束（创建人）"
        ))

    def _handle_create(self, args: list[str]):
        gid = self.bot_event.group_id
        uid = str(self.bot_event.user_id)
        if not args or args[0] not in ("接龙", "匹配"):
            self.api.send_msg(text("用法：/活动 创建 接龙|匹配 <标题> [参数]"))
            return
        if self.dbmanager.activity.get_active_activity(gid):
            self.api.send_msg(text("本群已有进行中的活动"))
            return
        kind = args[0]
        rest = args[1:]
        if kind == "接龙":
            if not rest:
                self.api.send_msg(text("用法：/活动 创建 接龙 <标题> [每人小时数]"))
                return
            title = rest[0]
            hours = 48.0
            if len(rest) > 1:
                try:
                    hours = float(rest[1])
                    if hours <= 0:
                        raise ValueError
                except ValueError:
                    self.api.send_msg(text("每人小时数必须为正数"))
                    return
            aid = self.dbmanager.activity.create_activity(
                gid, "relay", title, None, uid, hours_per_user=hours)
            self.api.send_msg(text(
                f"接龙活动「{title}」已创建（#{aid}）\n"
                f"每人限时 {hours:g} 小时\n"
                f"回复 /活动 加入 报名，报名完成后由创建人 /活动 开始"
            ))
        else:
            if len(rest) < 2:
                self.api.send_msg(text("用法：/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>"))
                return
            title = rest[0]
            deadline = _parse_deadline(" ".join(rest[1:]))
            if not deadline:
                self.api.send_msg(text("截止时间格式错误，示例：2026-09-15 20:00"))
                return
            aid = self.dbmanager.activity.create_activity(
                gid, "match", title, None, uid, deadline=deadline)
            self.api.send_msg(text(
                f"匹配活动「{title}」已创建（#{aid}）\n"
                f"截止时间 {deadline}\n"
                f"回复 /活动 加入 报名，报名完成后由创建人 /活动 开始"
            ))

    def _handle_join(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act or act["status"] != "open":
            self.api.send_msg(text("本群当前没有报名中的活动"))
            return
        if self.dbmanager.activity.get_member(act["id"], uid):
            self.api.send_msg(text("你已加入该活动"))
            return
        self.dbmanager.activity.add_member(act["id"], uid, self._sender_nickname())
        n = self.dbmanager.activity.count_members(act["id"])
        self.api.send_msg(text(f"已加入「{act['title']}」（当前 {n} 人）"))

    def _handle_leave(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有进行中的活动"))
            return
        member = self.dbmanager.activity.get_member(act["id"], uid)
        if not member:
            self.api.send_msg(text("你不在该活动中"))
            return
        if act["status"] == "open":
            self.dbmanager.activity.remove_member(act["id"], uid)
            if self.dbmanager.activity.count_members(act["id"]) == 0:
                self.dbmanager.activity.update_activity(act["id"], status="cancelled")
                self.api.send_msg(text("已退出，活动无人参加已取消"))
                return
            if str(act["created_by"]) == uid:
                first = self.dbmanager.activity.get_members(act["id"])[0]
                self.dbmanager.activity.update_activity(act["id"], created_by=first["user_id"])
                self.api.send_msg(text(f"已退出，创建人已转移给 {first['nickname']}"))
                return
            self.api.send_msg(text("已退出报名"))
        else:
            self._handle_leave_running(act, member)

    def _handle_leave_running(self, act: dict, member: dict):
        """进行中退出：接龙摘链（仅当轮到 TA 时顺延），匹配闭合环。"""
        self.dbmanager.activity.update_member(act["id"], member["user_id"], status="left")
        members = self.dbmanager.activity.get_members(act["id"])
        self._announce_group(act["group_id"], f"{member['nickname']} 已退出活动")
        if act["type"] == "relay":
            cur = current_turn(members)
            if cur and cur["user_id"] == member["user_id"]:
                if not _relay_advance(self.api, self.dbmanager, act, members, member["seq"]):
                    _finish_activity(self.api, self.dbmanager, act)
        else:
            _match_reconnect(self.api, self.dbmanager, act, member["user_id"], members)
            fresh = self.dbmanager.activity.get_members(act["id"])
            if all(m["status"] == "done" for m in fresh):
                _finish_activity(self.api, self.dbmanager, act)

    def _handle_start(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有活动"))
            return
        if act["status"] != "open":
            self.api.send_msg(text("活动已开始"))
            return
        if str(act["created_by"]) != uid and not self.super_user():
            self.api.send_msg(text("只有创建人才能开始活动"))
            return
        members = self.dbmanager.activity.get_members(act["id"])
        users = [m["user_id"] for m in members]
        nick_map = {m["user_id"]: m["nickname"] for m in members}
        if act["type"] == "relay":
            if not users:
                self.api.send_msg(text("接龙活动至少需要 1 人"))
                return
            assigns = relay_assignments(users)
        else:
            if len(users) < 2:
                self.api.send_msg(text("匹配活动至少需要 2 人"))
                return
            ring = build_ring(users)
            assigns = [(u, n, i + 1) for i, (u, n) in enumerate(ring)]
        self.dbmanager.activity.set_ring(act["id"], assigns)
        self.dbmanager.activity.update_activity(act["id"], status="running")
        now = _now()
        if act["type"] == "relay":
            first = assigns[0]
            self.dbmanager.activity.update_member(act["id"], first[0], received_at=now)
            self._send_private(
                int(first[0]),
                text(f"接龙活动「{act['title']}」开始！你是第 1 棒。\n"
                     f"请创作并私聊发送 /提交 附上作品，限时 {act['hours_per_user']:g} 小时。"),
            )
            self._announce_group(gid, f"接龙活动「{act['title']}」开始，{nick_map[first[0]]} 先来！")
        else:
            for uid_, next_uid, _seq in assigns:
                self._send_private(
                    int(uid_),
                    text(f"匹配活动「{act['title']}」开始！\n"
                         f"你的下家是：{nick_map[next_uid]}\n"
                         f"请为 TA 创作并私聊发送 /提交 附上作品，截止 {act['deadline']}。"),
                )
            self._announce_group(gid, f"匹配活动「{act['title']}」开始，请查看私聊！")

    def _handle_status(self, gid: int):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有进行中的活动"))
            return
        members = self.dbmanager.activity.get_members(act["id"])
        lines = [f"「{act['title']}」（{'匹配下家' if act['type'] == 'match' else '接龙'} #{act['id']}）"]
        status_map = {"done": "✓", "skipped": "跳过", "missed": "未交", "left": "退出", "pending": "…"}
        for m in members:
            lines.append(f"  {m['seq']}. {m['nickname']} {status_map.get(m['status'], m['status'])}")
        if act["type"] == "relay":
            cur = current_turn(members)
            if cur:
                lines.append(f"当前轮到：{cur['nickname']}")
            else:
                lines.append("接龙已完成")
        else:
            done = sum(1 for m in members if m["status"] == "done")
            lines.append(f"进度：{done}/{len(members)}")
            lines.append(f"截止：{act['deadline']}")
        self.api.send_msg(text("\n".join(lines)))

    def _handle_end(self, gid: int, uid: str):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有活动"))
            return
        if str(act["created_by"]) != uid and not self.super_user():
            self.api.send_msg(text("只有创建人才能结束活动"))
            return
        if act["status"] == "open":
            self.dbmanager.activity.update_activity(act["id"], status="cancelled")
            self.api.send_msg(text(f"活动「{act['title']}」已取消"))
        else:
            _finish_activity(self.api, self.dbmanager, act)
