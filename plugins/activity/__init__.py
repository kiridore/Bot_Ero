import json
import os
import re
from datetime import datetime, timedelta

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


def _parse_duration(raw: str) -> float | None:
    """解析接龙每人时限：'48'/'48小时'/'2天'（也接受 h/d）→ 小时数；非法返回 None。"""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(小时|天|h|d)?\s*", raw)
    if not m:
        return None
    hours = float(m.group(1))
    if m.group(2) in ("天", "d"):
        hours *= 24
    return hours if hours > 0 else None


def format_duration(hours: float) -> str:
    """48 → '2 天'；36 → '36 小时'。"""
    if hours % 24 == 0:
        return f"{int(hours // 24)} 天"
    return f"{hours:g} 小时"


_CREATE_KEYS = ("限时", "报名截止", "截止")


def _parse_create_params(tokens: list[str], kind: str) -> dict | str:
    """解析创建指令参数：返回 {'hours','deadline','signup_deadline','description'} 或错误消息。

    新语法（关键字）：<描述> 限时 <时限> 报名截止 <时间> 截止 <时间>
    旧语法兼容：无关键字时，接龙尾部识别时限、匹配尾部识别截止。
    """
    hours = 48.0
    deadline = None
    signup_deadline = None
    desc_tokens = list(tokens)
    if not any(t in _CREATE_KEYS for t in tokens):
        if kind == "relay" and tokens:
            h = _parse_duration(tokens[-1])
            if h is not None:
                hours = h
                desc_tokens = tokens[:-1]
        elif kind == "match":
            for window in (2, 1):
                if len(tokens) >= window:
                    d = _parse_deadline(" ".join(tokens[-window:]))
                    if d:
                        deadline = d
                        desc_tokens = tokens[:-window]
                        break
    first_key = next((i for i, t in enumerate(desc_tokens) if t in _CREATE_KEYS), None)
    if first_key is None:
        err = _check_deadlines_future(deadline, signup_deadline)
        if err:
            return err
        return {
            "hours": hours, "deadline": deadline,
            "signup_deadline": signup_deadline,
            "description": " ".join(desc_tokens).strip() or None,
        }
    description = " ".join(desc_tokens[:first_key]).strip() or None
    i = first_key
    seen = set()
    while i < len(desc_tokens):
        t = desc_tokens[i]
        if t in seen:
            return f"参数「{t}」重复"
        seen.add(t)
        if t == "限时":
            if i + 1 >= len(desc_tokens):
                return "限时缺少参数，示例：限时 48小时"
            h = _parse_duration(desc_tokens[i + 1])
            if h is None:
                return "限时格式错误，示例：48小时 / 2天"
            hours = h
            i += 2
            continue
        key = "signup_deadline" if t == "报名截止" else "deadline"
        d = None
        consumed = 0
        for window in (2, 1):
            if i + 1 + window <= len(desc_tokens):
                cand = _parse_deadline(" ".join(desc_tokens[i + 1:i + 1 + window]))
                if cand:
                    d = cand
                    consumed = 1 + window
                    break
        if d is None:
            return f"{t} 时间格式错误，示例：2026-09-15 20:00"
        if key == "signup_deadline":
            signup_deadline = d
        else:
            deadline = d
        i += consumed
    err = _check_deadlines_future(deadline, signup_deadline)
    if err:
        return err
    return {
        "hours": hours, "deadline": deadline,
        "signup_deadline": signup_deadline,
        "description": description,
    }


def _check_deadlines_future(deadline: str | None, signup_deadline: str | None) -> str | None:
    """截止/报名截止必须晚于当前时间，否则返回错误消息。"""
    now = _now()
    if deadline and deadline <= now:
        return "截止时间必须晚于当前时间"
    if signup_deadline and signup_deadline <= now:
        return "报名截止时间必须晚于当前时间"
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
            self._forward_work(act, members, member)
            if all(m["status"] in ("done", "left") for m in members):
                _finish_activity(self.api, self.dbmanager, act)

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
        """match：把 member 的作品转发给其下家（收件人已完成也照送）。"""
        recipient = self.dbmanager.activity.get_member(act["id"], member["next_user_id"])
        if not recipient or recipient["status"] == "left":
            return
        if recipient["user_id"] == member["user_id"]:
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
            "/活动 创建 接龙 <标题> [每人时限]（如 48小时 / 2天）\n"
            "/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>\n"
            "/活动 加入 / 退出\n"
            "/活动 开始（创建人）\n"
            "/活动 状态 / 结束（创建人）"
        ))

    def _handle_create(self, args: list[str]):
        gid = self.bot_event.group_id
        uid = str(self.bot_event.user_id)
        if not args or args[0] not in ("接龙", "匹配"):
            self.api.send_msg(text("用法：/活动 创建 接龙|匹配 <标题> [描述] [参数]"))
            return
        if self.dbmanager.activity.get_active_activity(gid):
            self.api.send_msg(text("本群已有进行中的活动"))
            return
        kind = args[0]
        rest = args[1:]
        if not rest:
            usage = ("用法：/活动 创建 接龙 <标题> [描述] [参数]\n"
                     "参数：限时 <时限> / 报名截止 <时间> / 截止 <时间>，如：\n"
                     "/活动 创建 接龙 端午 大家自由创作 报名截止 2026-08-10 20:00 截止 2026-08-20 20:00 限时 2天")
            self.api.send_msg(text(usage))
            return
        title = rest[0]
        params = _parse_create_params(rest[1:], "relay" if kind == "接龙" else "match")
        if isinstance(params, str):
            self.api.send_msg(text(params))
            return
        if kind == "接龙":
            aid = self.dbmanager.activity.create_activity(
                gid, "relay", title, params["description"], uid,
                hours_per_user=params["hours"],
                deadline=params["deadline"], signup_deadline=params["signup_deadline"])
            lines = [
                f"接龙活动「{title}」已创建（#{aid}）",
                f"每人限时 {format_duration(params['hours'])}",
            ]
        else:
            if not params["deadline"]:
                self.api.send_msg(text("匹配活动必须设定截止时间，示例：截止 2026-09-15 20:00"))
                return
            aid = self.dbmanager.activity.create_activity(
                gid, "match", title, params["description"], uid,
                deadline=params["deadline"], signup_deadline=params["signup_deadline"])
            lines = [
                f"匹配活动「{title}」已创建（#{aid}）",
                f"截止时间 {params['deadline']}",
            ]
        if params["description"]:
            lines.append(f"描述：{params['description']}")
        if params["signup_deadline"]:
            lines.append(f"报名截止：{params['signup_deadline']}（到点自动开始）")
        lines.append("回复 /活动 加入 报名，报名完成后由创建人 /活动 开始")
        self.api.send_msg(text("\n".join(lines)))

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
        err = _start_activity(self.api, self.dbmanager, act)
        if err:
            self.api.send_msg(text(err))

    def _handle_status(self, gid: int):
        act = self.dbmanager.activity.get_active_activity(gid)
        if not act:
            self.api.send_msg(text("本群没有进行中的活动"))
            return
        members = self.dbmanager.activity.get_members(act["id"])
        lines = [f"「{act['title']}」（{'匹配下家' if act['type'] == 'match' else '接龙'} #{act['id']}）"]
        if act.get("description"):
            lines.append(f"描述：{act['description']}")
        if act["status"] == "open":
            lines.append(f"状态：报名中（{len(members)} 人已报名）")
            if act.get("signup_deadline"):
                lines.append(f"报名截止：{act['signup_deadline']}")
            if act.get("deadline"):
                lines.append(f"截止：{act['deadline']}")
            for i, m in enumerate(members, 1):
                lines.append(f"  {i}. {m['nickname']}")
        else:
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
        f"轮到 {target['nickname']} 接力！请于 {format_duration(act['hours_per_user'])} 内完成，私聊 /提交 作品。",
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


def _warn_relay_deadline_conflict(api, act: dict, member_count: int):
    """接龙全局截止早于最晚理论完成时间（开始 + 人数×限时）时群公告警告。"""
    try:
        due = datetime.strptime(act["deadline"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return
    hours = act.get("hours_per_user") or 0
    worst_end = datetime.now() + timedelta(hours=hours) * member_count
    if worst_end > due:
        _announce_group(
            api, act["group_id"],
            f"⚠️ 提醒：截止 {act['deadline']} 早于最晚理论完成时间"
            f" {worst_end.strftime('%Y-%m-%d %H:%M:%S')}（{member_count} 人 × 每人"
            f" {format_duration(hours)}），到点未完成的接力将直接截断归档。",
        )


def _finish_activity(api, db, act: dict):
    now = _now()
    db.activity.update_activity(act["id"], status="finished", finished_at=now)
    fresh = db.activity.get_activity(act["id"])
    members = db.activity.get_members(act["id"])
    archive_mod.archive_activity(fresh, members)
    _announce_group(api, act["group_id"], f"活动「{act['title']}」结束，已归档！")


def _start_activity(api, db, act: dict) -> str | None:
    """开始活动：校验人数、生成链/环、置 running、私聊通知。返回错误消息或 None。

    供手动 /活动 开始 与心跳报名截止自动开始共用。
    """
    members = db.activity.get_members(act["id"])
    users = [m["user_id"] for m in members]
    nick_map = {m["user_id"]: m["nickname"] for m in members}
    if act.get("deadline") and act["deadline"] <= _now():
        return "截止时间已过，无法开始活动"
    if act["type"] == "relay":
        if not users:
            return "接龙活动至少需要 1 人"
        assigns = relay_assignments(users)
    else:
        if len(users) < 2:
            return "匹配活动至少需要 2 人"
        ring = build_ring(users)
        assigns = [(u, n, i + 1) for i, (u, n) in enumerate(ring)]
    db.activity.set_ring(act["id"], assigns)
    db.activity.update_activity(act["id"], status="running")
    now = _now()
    if act["type"] == "relay":
        if act.get("deadline"):
            _warn_relay_deadline_conflict(api, act, len(users))
        first = assigns[0]
        db.activity.update_member(act["id"], first[0], received_at=now)
        _send_private(
            api, int(first[0]),
            text(f"接龙活动「{act['title']}」开始！你是第 1 棒。\n"
                 f"请创作并私聊发送 /提交 附上作品，限时 {format_duration(act['hours_per_user'])}。"),
        )
        _announce_group(api, act["group_id"],
                        f"接龙活动「{act['title']}」开始，{nick_map[first[0]]} 先来！")
    else:
        for uid_, next_uid, _seq in assigns:
            _send_private(
                api, int(uid_),
                text(f"匹配活动「{act['title']}」开始！\n"
                     f"你的下家是：{nick_map[next_uid]}\n"
                     f"请为 TA 创作并私聊发送 /提交 附上作品，截止 {act['deadline']}。"),
            )
        _announce_group(api, act["group_id"], f"匹配活动「{act['title']}」开始，请查看私聊！")
    return None


@register_plugin
class ActivityTimerPlugin(Plugin):
    name = "activity_timer"
    description = "活动计时：接龙超时跳过、匹配截止结束"

    _last_scan = {}

    def match(self, event_type="meta") -> bool:
        if event_type != "meta":
            return False
        now = datetime.now()
        last = self._last_scan.get(type(self).__name__, 0)
        if now.timestamp() - last < 60:
            return False
        self._last_scan[type(self).__name__] = now.timestamp()
        return True

    def handle(self):
        try:
            self._scan()
        except Exception:
            logger.exception("ActivityTimer 处理异常")

    def _announce_group(self, group_id: int, text_body: str):
        _announce_group(self.api, group_id, text_body)

    def _scan(self):
        from .logic import is_timeout, current_turn
        now = datetime.now()
        # 报名截止到点 → 自动开始（人数不足则取消）
        for act in self.dbmanager.activity.get_active_activities():
            if act["status"] != "open" or not act.get("signup_deadline"):
                continue
            try:
                due = datetime.strptime(act["signup_deadline"], "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
            if now >= due:
                err = _start_activity(self.api, self.dbmanager, act)
                if err:
                    self.dbmanager.activity.update_activity(act["id"], status="cancelled")
                    self._announce_group(act["group_id"], f"报名截止，{err}，活动已取消")
        for act in self.dbmanager.activity.get_running_activities():
            members = self.dbmanager.activity.get_members(act["id"])
            if act["type"] == "relay":
                cur = current_turn(members)
                if cur and is_timeout(cur.get("received_at"), now, act.get("hours_per_user") or 0):
                    self.dbmanager.activity.update_member(
                        act["id"], cur["user_id"], status="skipped")
                    self._announce_group(act["group_id"], f"{cur['nickname']} 超时未完成，跳过")
                    members = self.dbmanager.activity.get_members(act["id"])
                    if not _relay_advance(self.api, self.dbmanager, act, members, cur["seq"]):
                        _finish_activity(self.api, self.dbmanager, act)
            deadline = act.get("deadline")
            try:
                due = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
            remaining = due - now
            if timedelta(0) < remaining <= timedelta(hours=24) and not act.get("pre_deadline_notified"):
                pending = [m["nickname"] for m in members if m["status"] == "pending"]
                done = sum(1 for m in members if m["status"] == "done")
                hours_left = remaining.total_seconds() / 3600
                lines = [
                    f"活动「{act['title']}」距截止还有 {hours_left:g} 小时！",
                    f"当前进度：{done}/{len(members)}",
                ]
                if pending:
                    lines.append("尚未提交：" + "、".join(pending))
                lines.append("请尽快私聊机器人 /提交 作品")
                self._announce_group(act["group_id"], "\n".join(lines))
                self.dbmanager.activity.update_activity(
                    act["id"], pre_deadline_notified=1)
            if now >= due:
                for m in members:
                    if m["status"] == "pending":
                        self.dbmanager.activity.update_member(
                            act["id"], m["user_id"], status="missed")
                _finish_activity(self.api, self.dbmanager, act)
