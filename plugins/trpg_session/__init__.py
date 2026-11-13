import os
import re
import time
from datetime import datetime
from pathlib import Path

from core.base import TimedHeartbeatPlugin, BOT_QQ, NICKNAME, SUPER_USER
from core.cq import at, text
from core.config import WEB_BASE_URL
from core.logger import logger
from core.onebot_client import (
    fetch_group_list, fetch_group_members, resolve_group_member_name, resolve_group_name,
)
from core.utils import register_plugin, download_image
from core import character_store as store
from core.trpg import growth, party, records, snapshots
from core.trpg.game_systems import DEFAULT_RULE, GAME_SYSTEMS, normalize_rule, rule_name
import core.context as runtime_context

# 记录图片允许的扩展名，与 core.trpg.records 的媒体名校验保持一致
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

RECORD_STATES = {"recording": "录制中", "ended": "已结束"}

COMMAND = "/跑团"
PARTY_SUBCMDS = frozenset({"准备", "取消准备", "名单", "规则"})
MAX_GATE_MEMBERS = 200
WEB_TRPG_URL = f"{WEB_BASE_URL}/trpg"

# 群名只用于展示：进程内缓存，取不到不缓存（下次重试）
_group_name_cache: dict[int, str] = {}

# 录制状态恢复：超过这个时长无新消息的残留录制一律终止
RESUME_WINDOW_SECONDS = 7 * 24 * 3600
# 群解散检测间隔（分钟，需能整除 60）
HEARTBEAT_MINUTES = 5
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
PUBLIC_RECORDS_URL = f"{WEB_BASE_URL}/trpg/records"


def cached_group_name(group_id) -> str:
    if group_id in _group_name_cache:
        return _group_name_cache[group_id]
    name = resolve_group_name(group_id)
    if name:
        _group_name_cache[group_id] = name
    return name


def record_state(path) -> str:
    """由文件推断状态：meta.end 为 null → 录制中；否则已结束。"""
    meta = records.read_meta(path) or {}
    return "recording" if not meta.get("end") else "ended"


def build_record_md(meta: dict, entries: list) -> str:
    """由 messages.jsonl 的结构化消息生成 record.md。"""
    lines = [
        "# 跑团记录\n",
        f"- 开始时间：{meta.get('start', '')}",
        f"- 结束时间：{meta.get('end') or ''}",
        "- 参与人：",
    ]
    for p in meta.get("participants", []):
        uid = p.get("user_id", "")
        label = f"{p.get('nickname', '?')} ({uid})"
        if uid == str(BOT_QQ):
            label += " Bot"
        if p.get("role"):
            label += f" [{p['role'].upper()}]"
        lines.append(f"  - {label}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for entry in entries:
        ts = datetime.fromtimestamp(entry["time"]).strftime("%H:%M:%S")
        sender = entry.get("nickname") or "未知"
        if entry.get("char_name"):
            sender = f"{entry['char_name']}({sender})"
        prefix = {"dm": "[DM] ", "ob": "[OB] "}.get(entry.get("role", ""), "")
        lines.append(f"[{ts}] **{prefix}{sender}**:")
        for seg in entry.get("segments", []):
            seg_type = seg.get("type", "")
            if seg_type == "text":
                lines.append(seg.get("text", ""))
            elif seg_type == "image":
                if seg.get("local"):
                    lines.append(f"![图片]({seg['local']})")
                else:
                    lines.append(f"[图片: {seg.get('file', '?')}]")
            elif seg_type == "at":
                lines.append(f"@{seg.get('qq', '')}")
        lines.append("")
    return "\n".join(lines)


def write_record_md(record_path) -> bool:
    """由 messages.jsonl 生成 record.md；失败只记日志。"""
    try:
        meta = records.read_meta(record_path)
        if meta is None:
            return False
        entries, skipped = records.iter_messages(record_path)
        if skipped:
            logger.warning("跑团记录 %s 跳过 %d 条损坏消息", record_path, skipped)
        with open(Path(record_path) / "record.md", "w", encoding="utf-8") as f:
            f.write(build_record_md(meta, entries))
        return True
    except Exception:
        logger.exception("生成 record.md 失败：%s", record_path)
        return False


def finalize_quietly(record_path, end_ts=None, reason: str = "") -> None:
    """自动终止：写 end 并生成 md；无群可发，不产生任何用户可见回执。"""
    try:
        records.finalize_record(record_path, end_ts)
    except Exception:
        logger.exception("写入跑团记录结束时间失败：%s", record_path)
    ok = write_record_md(record_path)
    if reason:
        logger.info("跑团记录自动结束（%s）：%s%s", reason, record_path, "" if ok else "（record.md 生成失败）")


def max_image_index(record_path) -> int:
    imgs = Path(record_path) / "imgs"
    if not imgs.is_dir():
        return 0
    best = 0
    for item in imgs.iterdir():
        matched = re.match(r"img_(\d+)\.", item.name)
        if matched:
            best = max(best, int(matched.group(1)))
    return best


def _parse_start(meta: dict) -> int | None:
    try:
        return int(datetime.strptime(meta["start"], TIME_FORMAT).timestamp())
    except (KeyError, TypeError, ValueError):
        return None


def resume_session(group_id: int, meta: dict, record_path) -> dict:
    """用磁盘上的 meta 重建录制会话，并在记录里留一条中断/恢复消息。"""
    start = datetime.fromtimestamp(_parse_start(meta) or time.time())
    participants = {}
    for person in meta.get("participants") or []:
        if isinstance(person, dict) and person.get("user_id") is not None:
            participants[str(person["user_id"])] = dict(person)
    session = {
        "start": start,
        "messages": [],
        "participants": participants,
        "roles": dict(meta.get("roles") or {}),
        "rules": meta.get("rules") or DEFAULT_RULE,
        "dir": Path(record_path),
        "img_count": max_image_index(record_path),
        "resume_banner": True,
        "paused": bool(meta.get("paused")),
        "paused_at": meta.get("paused_at"),
    }
    with runtime_context.recording_lock:
        runtime_context.recording_sessions[group_id] = session

    if session["paused"]:
        # 暂停中重启：不写「中断/恢复」消息，公告改成提示暂停
        return session

    interrupted_at = records.last_message_time(record_path)
    if interrupted_at:
        gap_text = (
            f"录制于 {datetime.fromtimestamp(interrupted_at).strftime('%Y-%m-%d %H:%M')} 中断，"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')} 恢复"
        )
    else:
        gap_text = f"{datetime.now().strftime('%Y-%m-%d %H:%M')} 恢复录制（此前无消息）"
    try:
        records.append_message(record_path, {
            "time": int(time.time()),
            "sender_type": "bot",
            "user_id": str(BOT_QQ),
            "nickname": NICKNAME,
            "char_name": "",
            "role": "",
            "segments": [{"type": "text", "text": gap_text}],
        })
    except Exception:
        logger.exception("写入中断/恢复消息失败：%s", record_path)
    return session


def _ensure_record_group_name(record_path, group_id) -> None:
    """记录的 meta 缺群名时补写一次（开录时 OneBot 不可达的情况下兜底）。"""
    try:
        meta = records.read_meta(record_path)
        if not meta or meta.get("group_name"):
            return
        name = cached_group_name(group_id)
        if not name:
            return
        meta["group_name"] = name
        records.rewrite_meta(record_path, meta)
    except Exception:
        logger.exception("补写群名失败：%s", record_path)


def recover_recordings() -> int:
    """启动时按磁盘状态重建录制：续录、超时终止、群解散终止。返回续录数量。"""
    root = records.records_root()
    if not root.is_dir():
        return 0
    groups = fetch_group_list()
    now = int(time.time())
    resumed = 0
    for group_path in sorted(root.iterdir()):
        if not group_path.is_dir():
            continue
        try:
            group_id = int(group_path.name)
        except ValueError:
            continue
        pending = []
        for record_path in sorted(group_path.iterdir()):
            if not record_path.is_dir():
                continue
            try:
                records.record_dir(group_id, record_path.name)
            except ValueError:
                continue
            meta = records.read_meta(record_path)
            if not meta or meta.get("version") != 2 or meta.get("end"):
                continue
            pending.append((meta, record_path))
        if not pending:
            continue
        pending.sort(key=lambda item: (item[0].get("start") or "", item[1].name), reverse=True)
        for index, (meta, record_path) in enumerate(pending):
            last_at = records.last_message_time(record_path) or _parse_start(meta) or now
            if groups is not None and group_id not in groups:
                finalize_quietly(record_path, last_at, "群已解散")
                continue
            if index > 0:
                finalize_quietly(record_path, last_at, "同群多条待恢复，仅续最新一条")
                continue
            if now - last_at > RESUME_WINDOW_SECONDS:
                finalize_quietly(record_path, last_at, "超过 7 天无新消息")
                continue
            _ensure_record_group_name(record_path, group_id)
            resume_session(group_id, meta, record_path)
            resumed += 1
    if resumed:
        logger.info("已从磁盘恢复 %d 场跑团录制", resumed)
    return resumed


def _auto_finish(group_id: int, reason: str) -> None:
    """运行期自动终止（群已解散）：弹出会话并归档。"""
    session = runtime_context.get_recording_session(group_id)
    if not session:
        return
    with runtime_context.recording_lock:
        runtime_context.recording_sessions.pop(group_id, None)
    path = session.get("dir")
    if path is None:
        return
    end_ts = records.last_message_time(path) or int(session["start"].timestamp())
    finalize_quietly(path, end_ts, reason)


@register_plugin
class TrpgSessionPlugin(TimedHeartbeatPlugin):
    name = "trpg_session"
    description = "跑团：准备/名单/记录（开始、结束、列表、查看）"

    def should_run_on_heartbeat(self, event_type: str) -> bool:
        """基类按固定时刻触发，这里改成每 HEARTBEAT_MINUTES 分钟一次。"""
        if event_type != "meta":
            return False
        now = datetime.now()
        if now.minute % HEARTBEAT_MINUTES:
            return False
        if not self._passes_weekday_filter(now) or not self._passes_annual_filter(now):
            return False
        key = now.strftime("%Y-%m-%d %H:%M")
        if self._last_run_minute.get(type(self).__name__) == key:
            return False
        self._last_run_minute[type(self).__name__] = key
        return True

    # ── 事件消息 ──────────────────────────────────────────

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _get_sender_nickname(self) -> str:
        sender = self.bot_event.sender
        if sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or f"用户{self.bot_event.user_id}"
        return f"用户{self.bot_event.user_id}"

    def _command_parts(self):
        parts = self._first_text().split()
        if not parts or parts[0] != COMMAND:
            return None
        return parts

    def match(self, message_type) -> bool:
        if self.should_run_on_heartbeat(message_type):
            return True
        if message_type == "notice":
            # 群名片变更：实时刷新 DM/观察者昵称（网页准备名单读的是文件名）
            return self.bot_event.notice_type == "group_card"
        if message_type != "message":
            return False
        msg = self._first_text()
        if not msg:
            return False
        if msg.startswith(".dm") or msg.startswith(".ob"):
            return True
        parts = self._command_parts()
        if parts is not None:
            sub = parts[1] if len(parts) > 1 else ""
            return sub == "" or sub in PARTY_SUBCMDS or sub == "记录"
        group_id = self.bot_event.group_id
        return group_id is not None and runtime_context.is_group_recording(group_id)

    def handle(self):
        try:
            if self.bot_event.post_type == "meta":
                self._on_heartbeat()
                return
            if self.bot_event.post_type == "notice":
                self._handle_card_change()
                return
            msg = self._first_text()
            if msg.startswith(".dm"):
                self._handle_set_role("dm")
            elif msg.startswith(".ob"):
                self._handle_set_role("ob")
            else:
                parts = self._command_parts()
                if parts is not None:
                    self._route(parts)
                elif self.bot_event.group_id and runtime_context.is_group_recording(self.bot_event.group_id):
                    self._record_user_message()
        except Exception:
            logger.exception("TrpgSession 处理异常")

    def _handle_card_change(self):
        """群名片变更：把新昵称写回 pending.json 的 role_names（只针对 DM/观察者）。"""
        raw = self.bot_event.raw
        group_id = raw.get("group_id")
        user_id = raw.get("user_id")
        if group_id is None or user_id is None:
            return
        nickname = str(raw.get("card_new") or raw.get("card") or "").strip()
        if not nickname:
            # 取消群名片时通知里只剩空串：现拉一次成员信息拿 QQ 昵称，别留着旧名片
            # 事件驱动的一次性查询，直接要最新的
            nickname = resolve_group_member_name(group_id, user_id, use_cache=False)
        if not nickname:
            return
        try:
            party.update_role_nickname(group_id, user_id, nickname)
        except OSError:
            logger.exception("更新群名片昵称失败")

    # ── 指令路由 ──────────────────────────────────────────

    def _route(self, parts: list):
        sub = parts[1] if len(parts) > 1 else ""
        if sub == "":
            self._handle_card()
        elif sub in PARTY_SUBCMDS:
            if self._reject_if_recording():
                return
            if sub == "准备":
                self._handle_prepare()
            elif sub == "取消准备":
                self._handle_unprepare()
            elif sub == "规则":
                self._handle_rule(parts[2:])
            else:
                self._handle_card()
        elif sub == "成长":
            self._handle_growth(parts[2:])
        elif sub == "记录":
            self._route_record(parts[2:])
        else:
            self._handle_card()

    def _route_record(self, args: list):
        sub = args[0] if args else "列表"
        if sub == "开始":
            self._handle_start(force=False)
        elif sub == "强制开始":
            self._handle_start(force=True)
        elif sub == "暂停":
            self._handle_pause()
        elif sub == "结束":
            self._handle_stop()
        elif sub.startswith("#"):
            self._handle_view(sub[1:])
        else:
            self._handle_list()

    # ── 心跳：恢复公告与群解散检测 ────────────────────

    def _on_heartbeat(self):
        self._send_resume_banners()
        active = list(runtime_context.recording_sessions)
        if not active:
            return
        groups = fetch_group_list()
        if groups is None:
            return
        for group_id in active:
            if group_id not in groups:
                _auto_finish(group_id, "群已解散")

    def _send_resume_banners(self):
        for group_id, session in list(runtime_context.recording_sessions.items()):
            if not session.get("resume_banner"):
                continue
            start_text = session["start"].strftime("%Y-%m-%d %H:%M")
            if session.get("paused"):
                message = text(
                    f"{start_text} 开始的跑团录制处于暂停状态，"
                    f"发送 /跑团 记录 开始 可继续（无需重新准备）")
            else:
                message = text(f"已恢复 {start_text} 开始的跑团录制，如需结束请由 DM 发送 /跑团 记录 结束")
            ret = self.api.call_api("send_group_msg", {
                "group_id": group_id,
                "message": [message],
            })
            if isinstance(ret, dict) and ret.get("status") == "ok":
                session["resume_banner"] = False
            else:
                logger.warning("恢复公告发送失败，下个心跳重试：群 %s", group_id)

    def _reject_if_recording(self) -> bool:
        group_id = self.bot_event.group_id
        if group_id is not None and runtime_context.is_group_recording(group_id):
            self.api.send_msg(text("录制中无法准备或查看准备名单，请先 /跑团 记录 结束"))
            return True
        return False

    # ── 规则设置 ──────────────────────────────────────────

    def _handle_rule(self, args: list):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团指令请在群内使用"))
            return
        if not args:
            current = party.current_rule(group_id)
            options = "\n".join(f"· {cfg['name']} → /跑团 规则 {rule_id}" for rule_id, cfg in GAME_SYSTEMS.items())
            self.api.send_msg(text(f"当前规则：{rule_name(current)}\n可选规则：\n{options}"))
            return
        if not self._is_dm_or_admin(group_id):
            self.api.send_msg(text("只有 DM 才能切换规则"))
            return
        rule_id = normalize_rule(args[0])
        if rule_id is None:
            self.api.send_msg(text("未知规则，可用：" + " / ".join(cfg["name"] for cfg in GAME_SYSTEMS.values())))
            return
        try:
            party.set_rule(group_id, rule_id)
        except OSError:
            logger.exception("保存规则失败")
            self.api.send_msg(text("保存规则失败，请稍后重试"))
            return
        self.api.send_msg(text(f"已将本群跑团规则设为 {rule_name(rule_id)}"))

    # ── 准备情况卡片 ──────────────────────────────────────

    def _group_title(self, group_id) -> str:
        return cached_group_name(group_id) or f"群 {group_id}"

    def _handle_card(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团指令请在群内使用"))
            return
        self.api.send_msg(*self._card_segments(group_id))

    def _human_members(self, group_id):
        """群成员名单，剔除机器人自己与其它机器人；接口不可用时返回 None。"""
        members = fetch_group_members(group_id)
        if members is None:
            return None
        return [m for m in members if not m.get("is_robot") and m["user_id"] != str(BOT_QQ)]

    def _card_segments(self, group_id) -> list:
        data = party.read_pending(group_id)
        prepared = data["prepared"]
        roles = data["roles"]
        members = self._human_members(group_id)
        member_ids = {m["user_id"] for m in members} if members is not None else None
        names = {m["user_id"]: m["nickname"] for m in members} if members is not None else {}

        def name_of(uid):
            return names.get(uid) or (prepared.get(uid) or {}).get("nickname") or uid

        dm_ids = [u for u, r in roles.items() if r == "dm" and (member_ids is None or u in member_ids)]
        ob_ids = [u for u, r in roles.items() if r == "ob" and (member_ids is None or u in member_ids)]
        pending = []
        if member_ids is not None:
            exempt = set(dm_ids) | set(ob_ids)
            pending = [u for u in member_ids if u not in exempt and u not in prepared]
        ready = [u for u in prepared if member_ids is None or u in member_ids]

        name = cached_group_name(group_id)
        if name:
            try:
                party.set_group_name(group_id, name)
            except OSError:
                logger.exception("保存群名失败")
        lines = [f"【{name or f'群 {group_id}'}】开团准备"]
        lines.append(f"DM：{name_of(dm_ids[0])}" if dm_ids else "DM：未设置（一人发送 .dm）")
        lines.append("观察者：" + ("、".join(name_of(u) for u in ob_ids) if ob_ids else "无"))
        lines.append(f"已准备 {len(ready)}/{len(ready) + len(pending)}：")
        for uid in sorted(ready, key=lambda u: prepared[u].get("prepared_at", "")):
            snap = prepared[uid]
            lines.append(
                f"· {name_of(uid)} → {snap.get('char_name') or '?'}"
                f"{self._card_suffix(self._display_snapshot(snap))}")
        if not ready:
            lines.append("· 暂无")

        segments = [text("\n".join(lines))]
        if pending:
            segments.append(text("\n未准备："))
            for uid in pending:
                segments.append(at(uid))
                segments.append(text(" "))
        elif member_ids is None:
            segments.append(text("\n（成员名单不可用，未准备者未知）"))
        return segments

    @staticmethod
    def _display_snapshot(snap: dict) -> dict:
        """展示用的快照：1.81.1 之前的快照没有 rules/occupation/age，按当前角色卡补上。"""
        if snap.get("rules"):
            return snap
        user_id = snap.get("user_id")
        char = None
        if user_id:
            char_id = snap.get("char_id")
            char = store.get_char(user_id, char_id) if char_id else None
            char = char or store.get_current(user_id)
        if not char:
            return snap
        merged = dict(snap)
        merged.update({
            "rules": char.get("rules") or "dnd5e",
            "race": char.get("race", ""),
            "class_name": char.get("class_name", ""),
            "level": int(char.get("level") or 1),
            "occupation": char.get("occupation", ""),
            "age": int(char.get("age") or 0),
        })
        return merged

    @staticmethod
    def _card_suffix(snap: dict) -> str:
        """准备名单里角色卡后面的括号：按规则显示不同字段，缺信息时不显示问号。"""
        if (snap.get("rules") or "dnd5e") == "coc7th":
            bits = [snap.get("occupation") or "无职业"]
            if snap.get("age"):
                bits.append(f"{snap['age']}岁")
            return f"（{' · '.join(bits)}）"
        race = snap.get("race") or ""
        clazz = snap.get("class_name") or ""
        level = int(snap.get("level") or 0)
        if not race and not clazz and level <= 1:
            return ""
        return f"（{race or '?'} {clazz or '?'} Lv.{level or '?'}）"

    # ── 准备 / 取消准备 ──────────────────────────────────

    def _handle_prepare(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团指令请在群内使用"))
            return
        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else ""
        if not user_id:
            return
        char = store.get_current(user_id)
        if not char:
            self.api.send_msg(text("你还没有角色卡，请到网页端创建后再准备：\n" + WEB_TRPG_URL))
            return
        group_rule = party.current_rule(group_id)
        card_rule = char.get("rules") or "dnd5e"
        if card_rule != group_rule:
            self.api.send_msg(text(
                f"本团规则是 {rule_name(group_rule)}，你的当前角色卡是 {rule_name(card_rule)}：\n"
                f"请切换角色卡（/跑团 角色 列表 → /跑团 角色 切换 <编号>），或让 DM 用 /跑团 规则 修改本团规则"
            ))
            return
        snapshot = {
            "user_id": user_id,
            "nickname": self._get_sender_nickname(),
            "char_id": char.get("id"),
            "char_name": char.get("char_name", ""),
            "rules": card_rule,
            "race": char.get("race", ""),
            "class_name": char.get("class_name", ""),
            "level": int(char.get("level") or 1),
            # 调查员卡没有种族/职业等级，改记职业与年龄供准备名单展示
            "occupation": char.get("occupation", ""),
            "age": int(char.get("age") or 0),
            "prepared_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            party.set_prepared(group_id, user_id, snapshot)
        except OSError:
            logger.exception("保存准备状态失败")
            self.api.send_msg(text("保存准备状态失败，请稍后重试"))
            return
        self.api.send_msg(*self._card_segments(group_id))

    def _handle_unprepare(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团指令请在群内使用"))
            return
        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else ""
        if not user_id:
            return
        data = party.read_pending(group_id)
        if user_id not in data["prepared"]:
            self.api.send_msg(text("你还没有准备"))
            return
        try:
            party.clear_prepared(group_id, user_id)
        except OSError:
            logger.exception("保存准备状态失败")
            self.api.send_msg(text("保存准备状态失败，请稍后重试"))
            return
        self.api.send_msg(*self._card_segments(group_id))

    # ── DM / 观察者标记 ──────────────────────────────────

    def _handle_set_role(self, role: str):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("角色设置只能在群聊中使用"))
            return
        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else "0"
        session = runtime_context.get_recording_session(group_id)
        if session:
            # 录制中只改记录 meta，不重建 pending.json
            roles = session.setdefault("roles", {})
            if role == "dm":
                for other in [k for k, v in roles.items() if v == "dm" and k != user_id]:
                    roles.pop(other)
            roles[user_id] = role
            entry = session.get("participants", {}).get(user_id)
            if entry:
                entry["role"] = role
            path = session.get("dir")
            if path is not None:
                try:
                    self._sync_meta(path, session)
                except Exception:
                    logger.exception("写入跑团记录角色失败")
            label = "DM" if role == "dm" else "观察者"
            notice = f"已将 {self._get_sender_nickname()} 设为{label}"
            runtime_context.record_bot_message(group_id, NICKNAME, notice)
            self.api.send_msg(text(notice))
            return
        try:
            party.set_role(group_id, user_id, role, nickname=self._get_sender_nickname())
        except OSError:
            logger.exception("保存角色标记失败")
            self.api.send_msg(text("保存角色设置失败，请稍后重试"))
            return
        self.api.send_msg(*self._card_segments(group_id))

    # ── 开录准入校验 ──────────────────────────────────────

    # ── 幕间成长 ──────────────────────────────────────────

    def _handle_growth(self, args: list):
        sender = str(self.bot_event.user_id or "")
        target = None
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = str(seg.get("data", {}).get("qq", ""))
                if qq and qq != "all":
                    target = qq
                    break
        target = target or sender
        if target != sender and not self._is_dm_or_admin(self.bot_event.group_id):
            self.api.send_msg(text("只有 DM 可以替他人结算幕间成长"))
            return
        char = store.get_current(target)
        if not char:
            self.api.send_msg(text("还没有角色卡，请到网页端创建 COC 调查员卡"))
            return
        if (char.get("rules") or "dnd5e") != "coc7th":
            self.api.send_msg(text("幕间成长是 COC 7th 功能，当前角色卡不是 COC 调查员卡"))
            return
        group_id = self.bot_event.group_id
        # 幕间成长是卡片级操作：不在录制中也应能结算（开录会清空 pending.json，
        # 结束后 current_rule 会回落默认规则，不能因此把成长锁死），只在录制中按本团规则拦
        session = runtime_context.get_recording_session(group_id) if group_id is not None else None
        if session:
            rule = session.get("rules") or party.DEFAULT_RULE
            if rule != "coc7th":
                self.api.send_msg(text(f"本团规则是 {rule_name(rule)}，幕间成长需要 COC 7th"))
                return
        pending = growth.checked_skills(char)
        if not pending:
            self.api.send_msg(text("没有已标记的技能：先用 .ra <技能名> 检定成功，才能获得成长标记"))
            return
        details, san_change = growth.settle(char)
        try:
            store.update_char(target, char.get("id"), char)
        except Exception:
            logger.exception("保存幕间成长结果失败")
            self.api.send_msg(text("保存成长结果失败，请稍后重试"))
            return
        name = char.get("char_name") or target
        lines = [f"{name} 的幕间成长（{len(details)} 项）"]
        for skill, before, roll, gain, after in details:
            if gain:
                lines.append(f"· {skill}：D100={roll} > {before} → +{gain}，{before} → {after}")
            else:
                lines.append(f"· {skill}：D100={roll} ≤ {before}，未增长")
        if san_change:
            lines.append(f"· 有技能达到 90% 或更高，SAN +{san_change}")
        lines.append("已清空本次成长标记")
        self.api.send_msg(text("\n".join(lines)))

    def _is_dm_or_admin(self, group_id) -> bool:
        user_id = str(self.bot_event.user_id or "")
        if user_id.isdigit() and int(user_id) in SUPER_USER:
            return True
        # 录制中 pending.json 已被清空，DM 身份以会话里的 roles 为准
        session = runtime_context.get_recording_session(group_id)
        roles = session.get("roles") if session else None
        if roles is None:
            roles = party.read_pending(group_id)["roles"]
        return roles.get(user_id) == "dm"

    def _check_gate(self, data: dict, members) -> list:
        """返回问题列表；空列表表示通过。问题项为 {text, at?}。"""
        if members is None:
            return [{"text": "无法获取群成员列表：OneBot 接口未响应，无法校验成员（可改用 /跑团 记录 强制开始）"}]
        if len(members) > MAX_GATE_MEMBERS:
            return [{"text": f"群成员 {len(members)} 人，超过校验上限 {MAX_GATE_MEMBERS} 人（可改用 /跑团 记录 强制开始）"}]
        member_ids = {m["user_id"] for m in members}
        roles = {u: r for u, r in data["roles"].items() if u in member_ids}
        prepared = data["prepared"]
        dm_ids = [u for u, r in roles.items() if r == "dm"]
        exempt = set(dm_ids) | {u for u, r in roles.items() if r == "ob"}
        players = [m["user_id"] for m in members if m["user_id"] not in exempt]

        problems = []
        if not dm_ids:
            problems.append({"text": "还没有 DM：请一人发送 .dm"})
        no_card = [u for u in players if store.get_current(u) is None]
        not_ready = [u for u in players if u not in prepared]
        if no_card:
            problems.append({"text": f"缺少角色卡（到 {WEB_TRPG_URL} 创建）：", "at": no_card})
        if not_ready:
            problems.append({"text": "尚未准备（发送 /跑团 准备）：", "at": not_ready})
        return problems

    def _send_problems(self, problems: list):
        segments = [text("无法开始录制，请先处理：")]
        for problem in problems:
            segments.append(text("\n· " + problem["text"]))
            for uid in problem.get("at", []):
                segments.append(at(uid))
                segments.append(text(" "))
        self.api.send_msg(*segments)

    # ── 开始录制 ──────────────────────────────────────────

    def _handle_start(self, force: bool = False):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return
        if not force and not self._is_dm_or_admin(group_id):
            self.api.send_msg(text("只有 DM 才能开始录制：请先由一人发送 .dm"))
            return

        if runtime_context.is_group_recording(group_id):
            session = runtime_context.get_recording_session(group_id) or {}
            if session.get("paused"):
                self._resume_recording(group_id, session)
            else:
                self.api.send_msg(text("当前已在录制中"))
            return

        data = party.read_pending(group_id)
        # 强制开始的场景往往就是成员接口坏了，不要再为取昵称去撞一次 5 秒超时
        members = None if force else self._human_members(group_id)
        if not force:
            problems = self._check_gate(data, members)
            if problems:
                self._send_problems(problems)
                return

        self._start_session(group_id, "跑团记录已开始——", data, members)

    def _start_session(self, group_id: int, notice: str, data: dict, members):
        start = datetime.now()
        path = records.ensure_record_dir(group_id, records.start_dir_name(start))
        roles = dict(data["roles"])
        prepared = data["prepared"]
        names = {m["user_id"]: m["nickname"] for m in (members or [])} if members else {}

        dm_ids = [u for u, r in roles.items() if r == "dm"]
        ob_ids = [u for u, r in roles.items() if r == "ob"]
        ordered = dm_ids + ob_ids + [
            u for u in sorted(prepared, key=lambda k: prepared[k].get("prepared_at", ""))
            if u not in dm_ids and u not in ob_ids
        ]
        participants = []
        for uid in ordered:
            snap = prepared.get(uid) or {}
            char = store.get_current(uid)
            person = {
                "user_id": uid,
                "nickname": names.get(uid) or snap.get("nickname") or uid,
                "char_name": snap.get("char_name") or (char or {}).get("char_name", ""),
                "role": roles.get(uid, ""),
                "char_id": snap.get("char_id") or (char or {}).get("id"),
            }
            if char:
                person["sheet_start"] = snapshots.sheet_snapshot(char)
            participants.append(person)

        meta = {
            "version": 2,
            "group_id": group_id,
            "group_name": "",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": None,
            "rules": party.current_rule(group_id),
            "roles": roles,
            "participants": participants,
        }
        records.rewrite_meta(path, meta)
        with runtime_context.recording_lock:
            runtime_context.recording_sessions[group_id] = {
                "start": start,
                "messages": [],
                "participants": {p["user_id"]: dict(p) for p in participants},
                "roles": dict(roles),
                "rules": meta["rules"],
                "dir": path,
                "img_count": 0,
            }
        self.api.send_msg(text(notice))

        try:
            party.clear_all(group_id)
        except OSError:
            logger.exception("清理准备状态失败")

        # 群名只用于展示：先回执再取，避免不可达的 OneBot HTTP 拖慢「已开始」
        name = cached_group_name(group_id)
        if name:
            meta["group_name"] = name
            try:
                records.rewrite_meta(path, meta)
            except Exception:
                logger.exception("写入群名失败")

    # ── 暂停 / 续录 ─────────────────────────────────────

    def _handle_pause(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return
        session = runtime_context.get_recording_session(group_id)
        if not session:
            self.api.send_msg(text("当前没有进行中的记录"))
            return
        if not self._is_dm_or_admin(group_id):
            self.api.send_msg(text("只有 DM 才能暂停录制"))
            return
        if session.get("paused"):
            self.api.send_msg(text("录制已经处于暂停状态，发送 /跑团 记录 开始 可以继续"))
            return

        now = datetime.now()
        # 暂停标记先入档，再切暂停状态（record_bot_message 在暂停后会被跳过）
        runtime_context.record_bot_message(group_id, NICKNAME, f"录制于 {now.strftime('%H:%M')} 暂停")
        with runtime_context.recording_lock:
            session["paused"] = True
            session["paused_at"] = int(now.timestamp())
        path = session.get("dir")
        if path is not None:
            self._write_pause_meta(path, True, int(now.timestamp()))
        self.api.send_msg(text(
            "录制已暂停：期间的对话不会写入记录。\n"
            "发送 /跑团 记录 开始 继续录制（无需重新准备）。"))

    def _resume_recording(self, group_id: int, session: dict):
        now = datetime.now()
        paused_at = session.get("paused_at")
        with runtime_context.recording_lock:
            session["paused"] = False
            session.pop("paused_at", None)
        path = session.get("dir")
        if path is not None:
            self._write_pause_meta(path, False, None)
        gap = ""
        if paused_at:
            minutes = max(0, int((now.timestamp() - paused_at) // 60))
            gap = f"（暂停 {minutes} 分钟）" if minutes else ""
        runtime_context.record_bot_message(
            group_id, NICKNAME, f"录制于 {now.strftime('%H:%M')} 恢复{gap}")
        start_dir = records.start_dir_name(session["start"])
        self.api.send_msg(text(
            f"已继续录制{gap}——\n查看：{PUBLIC_RECORDS_URL}/{group_id}/{start_dir}"))

    @staticmethod
    def _write_pause_meta(path, paused: bool, paused_at) -> None:
        meta = records.read_meta(path)
        if meta is None:
            return
        meta["paused"] = bool(paused)
        meta["paused_at"] = paused_at
        try:
            records.rewrite_meta(path, meta)
        except Exception:
            logger.exception("写入暂停状态失败：%s", path)

    # ── 结束录制 ──────────────────────────────────────────

    def _handle_stop(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        if not runtime_context.is_group_recording(group_id):
            self.api.send_msg(text("当前没有进行中的记录"))
            return

        if not self._is_dm_or_admin(group_id):
            self.api.send_msg(text("只有 DM 才能结束录制"))
            return

        session = runtime_context.get_recording_session(group_id)
        if not session:
            self.api.send_msg(text("内部错误：找不到录制会话"))
            return

        path = session.get("dir")
        start_dir = records.start_dir_name(session["start"])
        with runtime_context.recording_lock:
            runtime_context.recording_sessions.pop(group_id, None)

        if path is None:
            self.api.send_msg(text("记录数据缺失，无法结束"))
            return

        _ensure_record_group_name(path, group_id)
        if session.get("paused"):
            self._write_pause_meta(path, False, None)
        try:
            records.finalize_record(path)
        except Exception:
            # 结束时间写失败不阻断结束流程，网页侧该记录显示为「录制中」
            logger.exception("写入跑团记录结束时间失败")

        md_ok = write_record_md(path)
        tail = "" if md_ok else "\n（record.md 生成失败，网页仍可查看）"
        self.api.send_msg(text(
            f"跑团记录已结束——\n查看：{PUBLIC_RECORDS_URL}/{group_id}/{start_dir}{tail}"
        ))

    # ── 列表 ──────────────────────────────────────────

    def _record_dirs(self, group_id: int) -> list[str]:
        """该群已落盘的记录目录名（升序，只含合法目录名且已写入 messages.jsonl）。"""
        base = records.group_dir(group_id)
        if not base.is_dir():
            return []
        names = []
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            try:
                records.record_dir(group_id, entry.name)
            except ValueError:
                continue
            if (entry / "messages.jsonl").is_file():
                names.append(entry.name)
        return sorted(names)

    def _handle_list(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        names = self._record_dirs(group_id)
        if not names:
            self.api.send_msg(text("暂无保存的跑团记录"))
            return

        lines = ["已保存的跑团记录："]
        for i, name in enumerate(names, 1):
            path = records.record_dir(group_id, name)
            dt = datetime.strptime(name, records.START_DIR_FORMAT)
            count = len(records.iter_messages(path)[0])
            state = RECORD_STATES[record_state(path)]
            lines.append(f"[{i}] {dt.strftime('%Y-%m-%d %H:%M')}｜{state}｜{count} 条")
        self.api.send_msg(text("\n".join(lines)))

    # ── 查看 ──────────────────────────────────────────

    def _handle_view(self, index_str: str):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        try:
            idx = int(index_str)
        except ValueError:
            self.api.send_msg(text("请输入有效编号，格式：/跑团 记录 #数字"))
            return

        names = self._record_dirs(group_id)
        if not names:
            self.api.send_msg(text("暂无保存的跑团记录"))
            return

        if idx < 1 or idx > len(names):
            self.api.send_msg(text(f"编号无效，有效范围 1-{len(names)}"))
            return

        path = records.record_dir(group_id, names[idx - 1])
        meta = records.read_meta(path)
        if meta is None:
            self.api.send_msg(text("无法读取记录信息"))
            return

        header = [
            f"跑团记录 #{idx}",
            f"开始时间：{meta.get('start') or '?'}",
            f"结束时间：{meta.get('end') or '（录制中）'}",
            f"状态：{RECORD_STATES[record_state(path)]}",
        ]
        participants = meta.get("participants", [])
        if participants:
            header.append(f"参与人：{', '.join(p.get('nickname', '?') for p in participants)}")

        self.api.send_msg(text("\n".join(header)))

    # ── 记录用户消息 ──────────────────────────────────────────

    def _record_user_message(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            return
        # 跳过机器人自己的消息（避免 message_sent 事件导致重复录制）
        if self.bot_event.user_id and str(self.bot_event.user_id) == str(BOT_QQ):
            return

        session = runtime_context.get_recording_session(group_id)
        if not session or session.get("paused"):
            return

        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else "0"
        nickname = self._get_sender_nickname()
        char = store.get_current(user_id)
        char_name = (char or {}).get("char_name", "")
        role = session.get("roles", {}).get(user_id, "")
        ts = self.bot_event.time or int(time.time())

        person = {
            "nickname": nickname,
            "user_id": user_id,
            "char_name": char_name,
            "role": role,
        }
        if char:
            person["char_id"] = char.get("id")
            # 中途才开口的参与者：用首次发言时的卡作为 sheet_start
            person["sheet_start"] = snapshots.sheet_snapshot(char)
        with runtime_context.recording_lock:
            is_new = user_id not in session["participants"]
            session["participants"][user_id] = person
            # 内存副本供结束时合并转发使用
            session["messages"].append({
                "type": "user",
                "nickname": nickname,
                "user_id": user_id,
                "message": self.bot_event.message,
                "time": ts,
            })

        path = session.get("dir")
        if path is None:
            return
        entry = {
            "time": ts,
            "sender_type": "user",
            "user_id": user_id,
            "nickname": nickname,
            "char_name": char_name,
            "role": role,
            "segments": self._build_segments(session),
        }
        try:
            records.append_message(path, entry)
            if is_new:
                self._sync_meta(path, session)
        except Exception:
            logger.exception("写入跑团记录失败")

    def _build_segments(self, session: dict) -> list:
        segments = []
        for seg in self.bot_event.message:
            seg_type = seg.get("type")
            data = seg.get("data", {})
            if seg_type == "text":
                segments.append({"type": "text", "text": data.get("text", "")})
            elif seg_type == "image":
                segments.append(self._save_image(session, data.get("file", "")))
            elif seg_type == "at":
                segments.append({"type": "at", "qq": str(data.get("qq", ""))})
            else:
                segments.append({"type": "other"})
        return segments

    def _save_image(self, session: dict, file_name: str) -> dict:
        """图片落 imgs/img_NNNN.<ext>；任何失败都只标记该段不可用，不中断录制。"""
        try:
            url = self.api.get_image_url(file_name)
            if not url:
                return {"type": "image", "unavailable": True, "file": file_name}
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in IMAGE_EXTS:
                ext = ".jpg"
            with runtime_context.recording_lock:
                session["img_count"] = session.get("img_count", 0) + 1
                index = session["img_count"]
            # shortcut: 单条记录超过 9999 张图会生成 5 位序号，web 媒体路由校验将拒绝
            local = f"imgs/img_{index:04d}{ext}"
            ok, _ = download_image(url, str(session["dir"] / local))
            if not ok:
                return {"type": "image", "unavailable": True, "file": file_name}
            return {"type": "image", "local": local}
        except Exception:
            logger.exception("跑团记录图片入档失败")
            return {"type": "image", "unavailable": True, "file": file_name}

    def _sync_meta(self, path, session: dict):
        """把会话里的 roles / participants 重写进 meta.json。"""
        meta = records.read_meta(path)
        if meta is None:
            return
        meta["roles"] = dict(session.get("roles", {}))
        meta["participants"] = list(session.get("participants", {}).values())
        records.rewrite_meta(path, meta)
