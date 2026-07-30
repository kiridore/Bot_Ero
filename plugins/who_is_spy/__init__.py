from core.base import Plugin, BOT_QQ
from core.cq import text
from core.logger import logger
from core.utils import register_plugin
from core.database_manager import DbManager

from .room import (
    create_room, get_room, remove_room,
    add_player, remove_player, find_player_room, get_player, GAME_TYPES,
)
from .game import (
    start_game, collect_description, collect_vote,
    advance_to_voting, tally_votes, check_winner, advance_to_describe,
)
from .relay import (
    broadcast, broadcast_descriptions, broadcast_vote_instructions,
    broadcast_describe_instructions, broadcast_vote_result,
    broadcast_game_over, build_forward_nodes, send_forward_to_group,
)
from .titles import grant_game_titles

COMMANDS = frozenset({
    "/创建游戏", "/开始", "/加入", "/离开", "/退出",
    "/状态", "/放弃",
})


@register_plugin
class WhoIsSpyPlugin(Plugin):
    name = "who_is_spy"
    description = "谁是卧底：群聊创建房间，私聊匿名进行"

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
        self.api.call_api("send_private_msg", {
            "user_id": user_id,
            "message": message,
        })

    def match(self, event_type="message") -> bool:
        if event_type != "message":
            return False
        text_body = self._first_text()
        if not text_body:
            return False

        parts = text_body.split()
        if parts[0] in COMMANDS:
            self._mode = "command"
            self._cmd = parts[0]
            self._args = parts[1:]
            return True

        if self.bot_event.is_private and self.bot_event.user_id:
            room = find_player_room(self.bot_event.user_id)
            if room and room["phase"] not in ("waiting", "game_over"):
                self._mode = "game_input"
                self._game_room_id = room["room_id"]
                self._input_text = text_body
                return True

        return False

    def handle(self):
        try:
            if self._mode == "command":
                self._handle_command()
            elif self._mode == "game_input":
                self._handle_game_input()
        except Exception:
            logger.exception("WhoIsSpy 处理异常")

    def _handle_command(self):
        cmd = self._cmd
        args = self._args
        uid = self.bot_event.user_id
        if uid is None:
            return
        gid = self.bot_event.group_id

        if cmd == "/创建游戏" and gid:
            if not args or args[0] not in GAME_TYPES:
                types_str = "、".join(GAME_TYPES)
                self.api.send_msg(text(f"用法：/创建游戏 <类型> [人数]\n支持的类型：{types_str}"))
                return
            game_type = args[0]
            max_p = 6
            if len(args) > 1:
                try:
                    max_p = max(4, min(10, int(args[1])))
                except ValueError:
                    self.api.send_msg(text("人数必须为数字（4-10）"))
                    return
            try:
                rid = create_room(gid, uid, game_type, max_p)
                self.api.send_msg(text(
                    f"「{game_type}」房间 {rid} 已创建（{max_p}人局）\n"
                    f"请私聊机器人发送 /加入 {rid} 加入\n"
                    f"输入 /开始 {rid} 开始游戏"
                ))
            except RuntimeError as e:
                self.api.send_msg(text(str(e)))

        elif cmd == "/开始" and gid:
            if not args:
                self.api.send_msg(text("用法：/开始 <房间号>"))
                return
            rid = args[0]
            room = get_room(rid)
            if not room:
                self.api.send_msg(text("房间不存在"))
                return
            if room["group_id"] != gid:
                self.api.send_msg(text("该房间不属于本群"))
                return
            if str(uid) != room["creator_id"]:
                self.api.send_msg(text("只有房主才能开始游戏"))
                return
            result = start_game(room)
            if result != "ok":
                self.api.send_msg(text(result))
                return

            self.api.send_msg(text("游戏开始！请查看私聊查看自己的词条"))
            for pid, p in room["players"].items():
                role_label = "平民" if p["role"] == "civilian" else "卧底"
                self._send_private(
                    int(pid),
                    text(f"{p['alias']}，你的角色：{role_label}\n你的词条：{p['word']}"),
                )

            broadcast_describe_instructions(self.api, room)

        elif cmd == "/加入" and not gid:
            if not args:
                self.api.send_msg(text("用法：/加入 <房间号>"))
                return
            rid = args[0]
            nick = self._sender_nickname()
            result = add_player(rid, uid, nick)
            self.api.send_msg(text(result))
            if not result.startswith("已加入"):
                return

            room = get_room(rid)
            if room:
                n = len(room["players"])
                self.api.call_api("send_group_msg", {
                    "group_id": room["group_id"],
                    "message": [text(f"玩家 {nick} 已加入房间 {rid}（{n}/{room['max_players']}）")],
                })

        elif cmd in ("/离开", "/退出"):
            room = find_player_room(uid)
            if not room:
                self.api.send_msg(text("你不在任何房间中"))
                return
            rid = room["room_id"]
            nick = self._sender_nickname()
            result = remove_player(rid, uid)
            self.api.send_msg(text(result))

            room = get_room(rid)
            if room and room["phase"] != "waiting":
                self.api.call_api("send_group_msg", {
                    "group_id": room["group_id"],
                    "message": [text(f"玩家 {nick} 已退出房间 {rid}（游戏中弃权出局）")],
                })
                alive = [p for p in room["players"].values() if p["alive"]]
                if alive:
                    broadcast(self.api, room, [text(f"玩家 {nick} 退出游戏，当前存活 {len(alive)} 人")])
                from .game import check_winner
                winner = check_winner(room)
                if winner:
                    room["_winner"] = winner
                    room["phase"] = "game_over"
                    room["ready_descriptions"] = {}
                    room["votes"] = {}
                    broadcast_game_over(self.api, room, winner)
                    nodes = build_forward_nodes(room)
                    send_forward_to_group(self.api, room["group_id"], nodes)
                    remove_room(rid)

        elif cmd == "/状态":
            rid = args[0] if args else None
            room = None
            if rid:
                room = get_room(rid)
            if not room:
                room = find_player_room(uid)
            if not room:
                self.api.send_msg(text("房间不存在，或你不在房间中"))
                return
            lines = [
                f"房间 {room['room_id']}（{room.get('game_type', '?')}）",
                f"状态：{room['phase']}",
                f"人数：{len(room['players'])}/{room['max_players']}",
            ]
            if room["phase"] != "waiting":
                alive = sum(1 for p in room["players"].values() if p["alive"])
                lines.append(f"存活：{alive}/{len(room['players'])}")
                lines.append(f"轮次：{room['round_num']}")
            if room["phase"] == "waiting":
                players = sorted(
                    room["players"].items(),
                    key=lambda x: (x[1]["alias"],),
                )
                if players:
                    lines.append("玩家列表：")
                    for pid, p in players:
                        marker = "（房主）" if pid == room["creator_id"] else ""
                        lines.append(f"  {p['alias']} {p['nickname']}{marker}")
            self.api.send_msg(text("\n".join(lines)))

        elif cmd == "/放弃" and gid:
            if not args:
                self.api.send_msg(text("用法：/放弃 <房间号>"))
                return
            rid = args[0]
            room = get_room(rid)
            if not room:
                self.api.send_msg(text("房间不存在"))
                return
            if room["group_id"] != gid:
                self.api.send_msg(text("该房间不属于本群"))
                return
            if str(uid) != room["creator_id"] and not self.super_user():
                self.api.send_msg(text("只有房主或超管才能放弃游戏"))
                return
            game_type = room.get("game_type", "游戏")
            remove_room(rid)
            self.api.send_msg(text(f"「{game_type}」房间 {rid} 已解散"))

    def _handle_game_input(self):
        if self.bot_event.user_id is None:
            return
        room = get_room(self._game_room_id)
        if not room:
            self.api.send_msg(text("房间不存在或已解散"))
            return
        uid = str(self.bot_event.user_id)
        text_body = self._input_text

        if room["phase"] == "playing_describe":
            result = collect_description(room, uid, text_body)
            if isinstance(result, str):
                self.api.send_msg(text(result))
                return

            self.api.send_msg(text("描述已记录，等待其他玩家..."))

            if result is True:
                broadcast_descriptions(self.api, room)
                advance_to_voting(room)
                broadcast_vote_instructions(self.api, room)

        elif room["phase"] == "playing_vote":
            result = collect_vote(room, uid, text_body)
            if isinstance(result, str):
                self.api.send_msg(text(result))
                return

            self.api.send_msg(text("投票已记录，等待其他玩家..."))

            if result is True:
                eliminated = tally_votes(room)

                broadcast_vote_result(self.api, room, eliminated)

                winner = check_winner(room)
                if winner:
                    room["_winner"] = winner
                    room["phase"] = "game_over"

                    room["ready_descriptions"] = {}
                    room["votes"] = {}

                    broadcast_game_over(self.api, room, winner)

                    for pid, p in room["players"].items():
                        titles = grant_game_titles(
                            self.dbmanager, pid, p["role"], winner
                        )
                        if titles:
                            from plugins.title import get_title_def
                            names = []
                            for tid in titles:
                                d = get_title_def(tid)
                                if d:
                                    names.append(d.get("name", ""))
                            if names:
                                self._send_private(
                                    int(pid),
                                    text(f"获得称号：{' '.join(names)}"),
                                )

                    nodes = build_forward_nodes(room)
                    send_forward_to_group(self.api, room["group_id"], nodes)

                    remove_room(room["room_id"])
                else:
                    advance_to_describe(room)
                    broadcast_describe_instructions(self.api, room)
