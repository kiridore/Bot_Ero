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

    # ── 私聊提交 ──────────────────────────────────

    def _handle_submit(self, args: list[str]):
        uid = str(self.bot_event.user_id)
        if self.bot_event.user_id is None:
            return
        act = None
        if args and args[0].isdigit():
            act = self.dbmanager.activity.get_running_activity_for_user_and_id(
                uid, int(args[0]))
            if not act:
                self.api.send_msg(text("活动编号无效"))
                return
        else:
            acts = self.dbmanager.activity.get_running_activities_for_user(uid)
            if len(acts) == 1:
                act = acts[0]
            elif len(acts) > 1:
                ids = "、".join(str(a["id"]) for a in acts)
                self.api.send_msg(text(f"你参与了多个活动，请使用 /提交 <活动id>（{ids}）"))
                return
        if not act:
            self.api.send_msg(text("你不在任何进行中的活动中"))
            return
        member = self.dbmanager.activity.get_member(act["id"], uid)
        if not member or member["status"] != "pending":
            self.api.send_msg(text("你已提交过作品或不在活动中"))
            return
        if act["type"] == "relay":
            cur = current_turn(self.dbmanager.activity.get_members(act["id"]))
            if not cur or cur["user_id"] != uid:
                self.api.send_msg(text("还没轮到你提交"))
                return
        content, image_files = self._extract_submission()
        if not content and not image_files:
            self.api.send_msg(text("请随 /提交 附上作品（文字或图片）"))
            return
        saved = self._download_images(act["id"], member["seq"], image_files)
        if len(saved) != len(image_files):
            self.api.send_msg(text("作品图片下载失败，请重试"))
            return
        now = _now()
        self.dbmanager.activity.update_member(
            act["id"], uid, status="done", content=content or None,
            images=json.dumps(saved) if saved else None, submitted_at=now)
        self.api.send_msg(text("提交成功！"))
        members = self.dbmanager.activity.get_members(act["id"])
        if act["type"] == "relay":
            self._announce_group(act["group_id"],
                                 f"第 {member['seq']} 棒 {member['nickname']} 完成接力")
            if not _relay_advance(self.api, self.dbmanager, act, members, member["seq"]):
                _finish_activity(self.api, self.dbmanager, act)
        else:
            self._announce_group(act["group_id"], f"{member['nickname']} 提交了作品")
            if all(m["status"] == "done" for m in members):
                _finish_activity(self.api, self.dbmanager, act)
            else:
                self._forward_work(act, members, member)

    def _extract_submission(self) -> tuple[str, list[str]]:
        """从消息段提取正文与图片文件（命令文本之后的部分为正文）。"""
        text_parts, images = [], []
        for seg in self.bot_event.message:
            if seg.get("type") == "image":
                images.append(seg.get("data", {}).get("file", ""))
            elif seg.get("type") == "text":
                text_parts.append(seg.get("data", {}).get("text", "").strip())
        body = " ".join(text_parts).strip()
        if body.startswith("/提交"):
            body = body[len("/提交"):].strip()
        sp = body.split(" ", 1)
        if len(sp) == 2 and sp[0].isdigit():
            body = sp[1].strip()
        return body, [f for f in images if f]

    def _download_images(self, activity_id: int, seq: int, image_files: list[str]) -> list[str]:
        from core.utils import download_image
        saved = []
        for n, f in enumerate(image_files, 1):
            ext = os.path.splitext(f)[1] or ".jpg"
            local = archive_mod.image_path(activity_id, seq, n, ext)
            url = self.api.get_image_url(f)
            if not url:
                return []
            ok, _ = download_image(url, local)
            if not ok:
                return []
            saved.append(os.path.basename(local))
        return saved

    def _forward_work(self, act: dict, members: list[dict], member: dict):
        """match：把 member 的作品匿名转发给其下家。"""
        recipient = self.dbmanager.activity.get_member(act["id"], member["next_user_id"])
        if not recipient or recipient["status"] != "pending":
            return
        fresh = next((m for m in members if m["user_id"] == member["user_id"]), member)
        self._send_private(
            int(member["next_user_id"]),
            text(f"你收到了一份作品（活动「{act['title']}」）："),
            *self._work_segments(fresh),
        )

    def _work_segments(self, member: dict) -> list[dict]:
        return _work_segments(member)

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
        members = self.dbmanager.activity.get_members(act["id"])
        cur = current_turn(members)
        self.dbmanager.activity.update_member(act["id"], member["user_id"], status="left")
        members = self.dbmanager.activity.get_members(act["id"])
        self._announce_group(act["group_id"], f"{member['nickname']} 已退出活动")
        if act["type"] == "relay":
            if cur and cur["user_id"] == member["user_id"]:
                if not _relay_advance(self.api, self.dbmanager, act, members, member["seq"]):
                    _finish_activity(self.api, self.dbmanager, act)
        else:
            _match_reconnect(self.api, self.dbmanager, act, member["user_id"], members)
            fresh = self.dbmanager.activity.get_members(act["id"])
            if all(m["status"] in ("done", "left") for m in fresh):
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


# ── 模块级流转辅助（Task 5） ──

def _work_segments(member: dict) -> list[dict]:
    segs = []
    if member.get("content"):
        segs.append(text(member["content"]))
    try:
        names = json.loads(member["images"]) if member.get("images") else []
    except (TypeError, ValueError):
        names = []
    for name in names:
        segs.append({"type": "image", "data": {"file": name}})
    return segs


def _relay_advance(api, db, act: dict, members: list[dict], from_seq: int) -> bool:
    """把作品顺延给 from_seq 之后第一个 pending 成员。返回 False 表示链已走完。"""
    from .logic import next_pending, last_done
    target = next_pending(members, from_seq)
    if not target:
        return False
    prev = last_done(members, target["seq"])
    if prev and (prev["content"] or prev.get("images")):
        _send_private(
            api, int(target["user_id"]),
            text(f"接力作品（活动「{act['title']}」）："),
            *_work_segments(prev),
        )
    db.activity.update_member(act["id"], target["user_id"], received_at=_now())
    _announce_group(
        api, act["group_id"],
        f"轮到 {target['nickname']} 接力！请于 {act['hours_per_user']:g} 小时内完成，私聊 /提交 作品。",
    )
    return True


def _match_reconnect(api, db, act: dict, left_uid: str, members: list[dict]):
    """匹配环闭合：left_uid 的前驱 next 改为其后继（Y→X→D 退出 X 后变 Y→D）。"""
    pred = next((m for m in members if m["next_user_id"] == left_uid), None)
    if not pred:
        return
    left = next((m for m in members if m["user_id"] == left_uid), None)
    new_next = left["next_user_id"] if left else None
    db.activity.update_member(act["id"], pred["user_id"], next_user_id=new_next)
    if pred["status"] == "pending":
        _send_private(
            api, int(pred["user_id"]),
            text("你的下家已退出，请继续创作，活动截止时间不变。"),
        )


def _finish_activity(api, db, act: dict):
    now = _now()
    db.activity.update_activity(act["id"], status="finished", finished_at=now)
    fresh = db.activity.get_activity(act["id"])
    members = db.activity.get_members(act["id"])
    archive_mod.archive_activity(fresh, members)
    _announce_group(api, act["group_id"], f"活动「{act['title']}」结束，已归档！")
