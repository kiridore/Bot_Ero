import os
import time
from datetime import datetime

from core.base import Plugin, BOT_QQ, NICKNAME
from core.cq import text
from core.config import WEB_BASE_URL
from core.logger import logger
from core.onebot_client import resolve_group_name
from core.utils import register_plugin, download_image
from core import character_store as store
from core.trpg import records
import core.context as runtime_context

# 记录图片允许的扩展名，与 core.trpg.records 的媒体名校验保持一致
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

RECORD_STATES = {"recording": "录制中", "ended": "已结束·未导出", "exported": "已导出"}


def record_state(path) -> str:
    """由文件推断状态：meta.end 为 null → 录制中；record.md 存在 → 已导出。"""
    meta = records.read_meta(path) or {}
    if not meta.get("end"):
        return "recording"
    return "exported" if (path / "record.md").is_file() else "ended"


@register_plugin
class TrpgSessionPlugin(Plugin):
    name = "trpg_session"
    description = "跑团记录：开始/结束/导出/列表/查看"

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

    def match(self, message_type) -> bool:
        if message_type != "message":
            return False
        msg = self._first_text()
        if not msg:
            return False
        if msg.startswith("/跑团记录") or msg.startswith(".dm") or msg.startswith(".ob"):
            return True
        group_id = self.bot_event.group_id
        if group_id is not None and runtime_context.is_group_recording(group_id):
            return True
        return False

    def handle(self):
        try:
            msg = self._first_text()
            if msg.startswith("/跑团记录"):
                self._route_command(msg)
            elif msg.startswith(".dm"):
                self._handle_set_role("dm")
            elif msg.startswith(".ob"):
                self._handle_set_role("ob")
            elif self.bot_event.group_id and runtime_context.is_group_recording(self.bot_event.group_id):
                self._record_user_message()
        except Exception:
            logger.exception("TrpgSession 处理异常")

    # ── 指令路由 ──────────────────────────────────────────

    def _route_command(self, msg: str):
        parts = msg.split()
        sub = parts[1] if len(parts) > 1 else ""

        if sub == "开始":
            self._handle_start()
        elif sub == "强制开始":
            self._handle_force_start()
        elif sub == "结束":
            self._handle_stop()
        elif sub == "导出":
            self._handle_export()
        elif parts[0] == "/跑团记录" and (sub == "列表" or not sub):
            self._handle_list()
        elif parts[0] == "/跑团记录" and sub and sub.startswith("#"):
            self._handle_view(sub[1:])
        else:
            self._handle_list()

    # ── 记录目录 ──────────────────────────────────────────

    def _fetch_group_name(self, group_id: int) -> str:
        # 走 HTTP 短超时接口：call_api 走 WS 时无响应要等 30 秒，会把录制开始拖住
        try:
            return resolve_group_name(group_id)
        except Exception:
            logger.exception("获取群名失败")
            return ""

    def _sync_meta(self, path, session: dict):
        """把会话里的 roles / participants 重写进 meta.json。"""
        meta = records.read_meta(path)
        if meta is None:
            return
        meta["roles"] = dict(session.get("roles", {}))
        meta["participants"] = list(session.get("participants", {}).values())
        records.rewrite_meta(path, meta)

    def _start_session(self, group_id: int, notice: str):
        start = datetime.now()
        path = records.ensure_record_dir(group_id, records.start_dir_name(start))
        roles = dict(runtime_context.group_roles.get(group_id, {}))
        meta = {
            "version": 2,
            "group_id": group_id,
            "group_name": "",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": None,
            "roles": roles,
            "participants": [],
        }
        records.rewrite_meta(path, meta)
        with runtime_context.recording_lock:
            runtime_context.recording_sessions[group_id] = {
                "start": start,
                "messages": [],
                "participants": {},
                "roles": roles,
                "dir": path,
                "img_count": 0,
            }
        self.api.send_msg(text(notice))
        # 群名只用于展示：先回执再取，避免不可达的 OneBot HTTP 拖慢「已开始」
        name = self._fetch_group_name(group_id)
        if name:
            meta["group_name"] = name
            try:
                records.rewrite_meta(path, meta)
            except Exception:
                logger.exception("写入群名失败")

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

    # ── DM/OB 角色设置 ──────────────────────────────────

    def _handle_set_role(self, role: str):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("角色设置只能在群聊中使用"))
            return
        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else "0"
        # 先清空该用户在当前群的旧角色
        if group_id not in runtime_context.group_roles:
            runtime_context.group_roles[group_id] = {}
        runtime_context.group_roles[group_id][user_id] = role
        # 如果在录制中，同步到 session 与 meta.json
        session = runtime_context.get_recording_session(group_id)
        if session and "roles" in session:
            session["roles"][user_id] = role
            if user_id in session["participants"]:
                session["participants"][user_id]["role"] = role
            if session.get("dir") is not None:
                try:
                    self._sync_meta(session["dir"], session)
                except Exception:
                    logger.exception("写入跑团记录角色失败")
        label = "DM" if role == "dm" else "观察者"
        notice = f"已将 {self._get_sender_nickname()} 设为{label}"
        runtime_context.record_bot_message(group_id, NICKNAME, notice)
        self.api.send_msg(text(notice))

    # ── 开始录制 ──────────────────────────────────────────

    def _handle_start(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        if runtime_context.is_group_recording(group_id):
            self.api.send_msg(text("当前已在录制中"))
            return

        # 检查是否有上次未导出的记录
        unexported = runtime_context.get_last_completed(group_id)
        if unexported:
            self.api.send_msg(text(
                "上次记录尚未导出！请先使用 /跑团记录 导出 保存记录，"
                "或使用 /跑团记录 强制开始 放弃并重新开始"
            ))
            return

        self._start_session(group_id, "跑团记录已开始——")

    def _handle_force_start(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        if runtime_context.is_group_recording(group_id):
            self.api.send_msg(text("当前已在录制中"))
            return

        # 丢弃未导出记录
        runtime_context.pop_last_completed(group_id)

        self._start_session(group_id, "已丢弃上次记录，跑团记录已开始——")

    # ── 结束录制 ──────────────────────────────────────────

    def _handle_stop(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        if not runtime_context.is_group_recording(group_id):
            self.api.send_msg(text("当前没有进行中的记录"))
            return

        session = runtime_context.get_recording_session(group_id)
        if not session:
            self.api.send_msg(text("内部错误：找不到录制会话"))
            return

        end_time = datetime.now()
        messages = session["messages"]

        # 按时间排序，同时间用户消息排在 bot 消息前面
        messages.sort(key=lambda m: (m.get("time", 0), 1 if m.get("type") == "bot" else 0))

        path = session.get("dir")
        if path is not None:
            try:
                meta = records.read_meta(path)
                if meta is not None:
                    meta["end"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    records.rewrite_meta(path, meta)
            except Exception:
                # 结束时间写失败不阻断结束流程，网页侧该记录显示为「录制中」
                logger.exception("写入跑团记录结束时间失败")

        with runtime_context.recording_lock:
            runtime_context.recording_sessions.pop(group_id, None)
            runtime_context.last_completed[group_id] = {
                "start": session["start"],
                "end": end_time,
                "messages": messages,
                "participants": session["participants"],
                "roles": session.get("roles", {}),
                "dir": path,
            }

        if not messages:
            self.api.send_msg(text("跑团记录已结束——\n（无记录内容）"))
            return

        self._send_forward(group_id, messages)
        self.api.send_msg(text("跑团记录已结束——"))

    # ── 导出到磁盘 ──────────────────────────────────────────

    def _handle_export(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        if runtime_context.is_group_recording(group_id):
            self.api.send_msg(text("录制中无法导出，请先结束录制"))
            return

        recording = runtime_context.pop_last_completed(group_id)
        if not recording:
            self.api.send_msg(text("没有可导出的记录"))
            return

        start_dir = records.start_dir_name(recording["start"])
        path = recording.get("dir") or records.record_dir(group_id, start_dir)

        try:
            meta = records.read_meta(path)
            if meta is None:
                self.api.send_msg(text("记录数据缺失，无法导出"))
                return

            entries, skipped = records.iter_messages(path)
            if skipped:
                logger.warning("跑团记录 %s 跳过 %d 条损坏消息", start_dir, skipped)

            with open(path / "record.md", "w", encoding="utf-8") as f:
                f.write(self._build_record_md(meta, entries))

            self.api.send_msg(text(
                f"导出成功：{start_dir}，共 {len(entries)} 条消息\n"
                f"查看：{WEB_BASE_URL}/trpg/records/{group_id}/{start_dir}"
            ))

        except Exception as e:
            logger.exception("导出记录失败")
            self.api.send_msg(text(f"导出失败：{e}"))

    def _build_record_md(self, meta: dict, entries: list) -> str:
        """由 messages.jsonl 的结构化消息生成 record.md（格式与旧纯文本导出一致）。"""
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

    # ── 列表 ──────────────────────────────────────────

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
            self.api.send_msg(text("请输入有效编号，格式：/跑团记录 #数字"))
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
        if not session:
            return

        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else "0"
        nickname = self._get_sender_nickname()
        char = store.get_current(user_id)
        char_name = (char or {}).get("char_name", "")
        role = session.get("roles", {}).get(user_id, "")
        ts = self.bot_event.time or int(time.time())

        with runtime_context.recording_lock:
            is_new = user_id not in session["participants"]
            session["participants"][user_id] = {
                "nickname": nickname,
                "user_id": user_id,
                "char_name": char_name,
                "role": role,
            }
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

    # ── 合并转发 ──────────────────────────────────────────

    def _send_forward(self, group_id: int, messages: list):
        nodes = []
        for entry in messages:
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": entry.get("user_id", "0"),
                    "nickname": entry.get("nickname", ""),
                    "content": entry.get("message", []),
                },
            })

        if nodes:
            self.api.call_api("send_group_forward_msg", {
                "group_id": group_id,
                "messages": nodes,
            })
