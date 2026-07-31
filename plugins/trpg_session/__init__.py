import os
import json
import time
import re
from datetime import datetime

from core.base import Plugin, BOT_QQ
from core.cq import text
from core.logger import logger
from core.utils import register_plugin, download_image
import core.context as runtime_context


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
        # 如果在录制中，同步到 session
        session = runtime_context.get_recording_session(group_id)
        if session and "roles" in session:
            session["roles"][user_id] = role
        label = "DM" if role == "dm" else "观察者"
        self.api.send_msg(text(f"已将 {self._get_sender_nickname()} 设为{label}"))

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

        self.api.send_msg(text("跑团记录已开始——"))
        session_roles = dict(runtime_context.group_roles.get(group_id, {}))
        with runtime_context.recording_lock:
            runtime_context.recording_sessions[group_id] = {
                "start": datetime.now(),
                "messages": [],
                "participants": {},
                "roles": session_roles,
            }

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

        self.api.send_msg(text("已丢弃上次记录，跑团记录已开始——"))
        session_roles = dict(runtime_context.group_roles.get(group_id, {}))
        with runtime_context.recording_lock:
            runtime_context.recording_sessions[group_id] = {
                "start": datetime.now(),
                "messages": [],
                "participants": {},
                "roles": session_roles,
            }

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

        with runtime_context.recording_lock:
            runtime_context.recording_sessions.pop(group_id, None)
            runtime_context.last_completed[group_id] = {
                "start": session["start"],
                "end": end_time,
                "messages": messages,
                "participants": session["participants"],
                "roles": session.get("roles", {}),
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

        start_str = recording["start"].strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"server_data/trpg_records/{group_id}/{start_str}"
        imgs_dir = f"{folder_name}/imgs"

        try:
            os.makedirs(imgs_dir, exist_ok=True)

            # 收集参与人
            roles = recording.get("roles", {})
            participants = list(recording["participants"].values())
            if not any(p["user_id"] == str(BOT_QQ) for p in participants):
                participants.append({"nickname": "小埃同学", "user_id": str(BOT_QQ)})

            # 参与者加上角色和索引
            for p in participants:
                uid = p["user_id"]
                p["role"] = roles.get(uid, "")

            # 写 meta.json（含 qq 供后续 web 展示用）
            meta = {
                "start": recording["start"].strftime("%Y-%m-%d %H:%M:%S"),
                "end": recording["end"].strftime("%Y-%m-%d %H:%M:%S"),
                "participants": participants,
            }
            with open(f"{folder_name}/meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            # 写 record.md
            def _role_prefix(uid: str) -> str:
                r = roles.get(uid, "")
                if r == "dm":
                    return "[DM] "
                if r == "ob":
                    return "[OB] "
                return ""

            md_lines = [
                "# 跑团记录\n",
                f"- 开始时间：{meta['start']}",
                f"- 结束时间：{meta['end']}",
                "- 参与人：",
            ]
            for p in participants:
                uid = p["user_id"]
                r = roles.get(uid, "")
                label = _role_prefix(uid) + f"{p['nickname']} ({uid})"
                if uid == str(BOT_QQ):
                    label += " Bot"
                if r:
                    label += f" [{r.upper()}]"
                md_lines.append(f"  - {label}")
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

            img_counter = 0
            char_cache = {}
            for entry in recording["messages"]:
                ts = datetime.fromtimestamp(entry["time"]).strftime("%H:%M:%S")
                uid = entry.get("user_id", "")
                sender = entry.get("nickname", "未知")
                # 有角色卡时显示 角色名(昵称)
                if uid and uid not in char_cache:
                    try:
                        char_cache[uid] = self.dbmanager.character.current(uid)
                    except Exception:
                        char_cache[uid] = None
                char = char_cache.get(uid)
                if char:
                    sender = f"{char.get('char_name', '')}({sender})"
                md_lines.append(f"[{ts}] **{_role_prefix(uid)}{sender}**:")
                for seg in entry.get("message", []):
                    seg_type = seg.get("type", "")
                    seg_data = seg.get("data", {})
                    if seg_type == "text":
                        md_lines.append(seg_data.get("text", ""))
                    elif seg_type == "image":
                        file_name = seg_data.get("file", "")
                        if file_name:
                            img_counter += 1
                            ext = os.path.splitext(file_name)[1] or ".jpg"
                            local_name = f"img_{img_counter:04d}{ext}"
                            local_path = f"{imgs_dir}/{local_name}"
                            try:
                                url = self.api.get_image_url(file_name)
                                if url:
                                    download_image(url, local_path)
                                    md_lines.append(f"![图片](imgs/{local_name})")
                                else:
                                    md_lines.append(f"[图片: {file_name}]")
                            except Exception:
                                md_lines.append(f"[图片: {file_name}]")
                    elif seg_type == "at":
                        qq = seg_data.get("qq", "")
                        md_lines.append(f"@{qq}")
                md_lines.append("")

            with open(f"{folder_name}/record.md", "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))

            self.api.send_msg(text(f"导出成功：{start_str}，共 {len(recording['messages'])} 条消息"))

        except Exception as e:
            logger.exception("导出记录失败")
            self.api.send_msg(text(f"导出失败：{e}"))

    # ── 列表 ──────────────────────────────────────────

    def _handle_list(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("跑团记录只能在群聊中使用"))
            return

        rec_dir = f"server_data/trpg_records/{group_id}"
        if not os.path.isdir(rec_dir):
            self.api.send_msg(text("暂无保存的跑团记录"))
            return

        folders = sorted([d for d in os.listdir(rec_dir) if os.path.isdir(f"{rec_dir}/{d}")])
        if not folders:
            self.api.send_msg(text("暂无保存的跑团记录"))
            return

        lines = ["已保存的跑团记录："]
        for i, folder in enumerate(folders, 1):
            try:
                dt = datetime.strptime(folder, "%Y-%m-%d_%H-%M-%S")
                lines.append(f"[{i}] {dt.strftime('%Y-%m-%d %H:%M')}")
            except ValueError:
                lines.append(f"[{i}] {folder}")
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

        rec_dir = f"server_data/trpg_records/{group_id}"
        if not os.path.isdir(rec_dir):
            self.api.send_msg(text("暂无保存的跑团记录"))
            return

        folders = sorted([d for d in os.listdir(rec_dir) if os.path.isdir(f"{rec_dir}/{d}")])
        if idx < 1 or idx > len(folders):
            self.api.send_msg(text(f"编号无效，有效范围 1-{len(folders)}"))
            return

        meta_path = f"{rec_dir}/{folders[idx - 1]}/meta.json"
        if not os.path.isfile(meta_path):
            self.api.send_msg(text("无法读取记录信息"))
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            self.api.send_msg(text("记录文件损坏"))
            return

        header = [
            f"跑团记录 #{idx}",
            f"开始时间：{meta.get('start', '?')}",
            f"结束时间：{meta.get('end', '?')}",
        ]
        participants = meta.get("participants", [])
        if participants:
            names = [p.get("nickname", "?") for p in participants]
            header.append(f"参与人：{', '.join(names)}")

        self.api.send_msg(text("\n".join(header)))

    # ── 记录用户消息 ──────────────────────────────────────────

    def _record_user_message(self):
        group_id = self.bot_event.group_id
        if group_id is None:
            return
        # 跳过机器人自己的消息（避免 message_sent 事件导致重复录制）
        if self.bot_event.user_id:
            from core.base import BOT_QQ
            if str(self.bot_event.user_id) == str(BOT_QQ):
                return

        session = runtime_context.get_recording_session(group_id)
        if not session:
            return

        user_id = str(self.bot_event.user_id) if self.bot_event.user_id else "0"
        nickname = self._get_sender_nickname()

        entry = {
            "type": "user",
            "nickname": nickname,
            "user_id": user_id,
            "message": self.bot_event.message,
            "time": self.bot_event.time or int(time.time()),
        }

        with runtime_context.recording_lock:
            session["messages"].append(entry)
            if user_id not in session["participants"]:
                session["participants"][user_id] = {"nickname": nickname, "user_id": user_id}

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
