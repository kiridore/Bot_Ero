"""注册插件（M1 community-registration）：/注册 流程与 /同意EULA 凭证。

定稿共识（2026-10-10 三轮质询）：显式 /注册 开始；会话内存态、同意持久化；
播种默认功能包；注册完成经内部通知发资料卡。文案按所有者定稿逐句原样。
"""
import random
import time
from pathlib import Path

from core import config
from core.base import CommandPlugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

_STAGE_EULA_SENT = "eula_sent"
_SESSIONS: dict[int, str] = {}  # 类级 dict 跨事件保留（同 TimedHeartbeatPlugin 先例）

# 大小写不敏感归一：ASCII 字母 lower 后比对
_CI_COMMANDS = {"/注册": "/注册", "/同意eula": "/同意EULA"}


def _ci_ascii(word: str) -> str:
    return "".join(c.lower() if c.isascii() else c for c in word)


def _eula_path() -> Path:
    path = Path(config.REGISTER_EULA_FILE)
    return path if path.is_absolute() else config.PROJECT_ROOT / path


@register_plugin
class RegisterPlugin(CommandPlugin):
    name = 'register'
    description = '公开部署的注册流程与《用户协议》同意。'
    COMMANDS = ("/注册", "/同意EULA")

    def match(self, event_type="message"):
        if event_type != "message":
            return False
        first = self._first_text()
        if not first:
            return False
        parts = first.split()
        canonical = _CI_COMMANDS.get(_ci_ascii(parts[0]))
        if canonical is None:
            return False
        self.cmd = canonical
        self.args = parts[1:]
        return True

    # Ruling：注册是时序敏感的分段对话——统一输出在事件结束时集中送达，
    # 无法承载段间停顿；此插件直接发送（提案 design 已记录该例外）。
    def _send(self, segment):
        self.api.send_private_msg(segment)

    def _pause(self, seconds=None):
        time.sleep(seconds if seconds is not None else random.uniform(2, 3))

    def _seed_default_pack(self, uid):
        from core.feature_packs import FEATURE_PACKS
        from core.db.plugin_settings import set_user_plugins
        pack = FEATURE_PACKS.get(config.REGISTER_DEFAULT_PACK)
        if not pack:
            logger.error("注册播种失败：功能包 %s 未定义", config.REGISTER_DEFAULT_PACK)
            return
        set_user_plugins(self.dbmanager.conn, uid, pack["plugins"], True)

    def handle(self):
        uid = self.bot_event.user_id
        if uid is None:
            return
        if self.bot_event.group_id is not None:
            self._send(text("请先添加我为好友，在私聊中完成注册~"))
            return
        community = self.dbmanager.community

        if self.cmd == "/注册":
            if community.is_registered(uid):
                self._send(text("你已经完成注册啦"))
                return
            self._send(text("现在开始注册流程，大概需要5分钟~"))
            self._pause()
            self._send(text("首先需要阅读一下我们的《用户协议》，里面一定有很多你关心的内容，务必看过之后再同意哦"))
            self._pause()
            self.api.send_forward_msg([text(_eula_path().read_text(encoding="utf-8"))])
            self._pause(5)
            self._send(text("如果看完后同意，请使用 “/同意EULA”指令继续"))
            _SESSIONS[uid] = _STAGE_EULA_SENT
            return

        # /同意EULA
        if community.is_registered(uid):
            self._send(text("你已经完成注册啦"))
            return
        if _SESSIONS.get(uid) != _STAGE_EULA_SENT:
            self._send(text("先发 /注册 开始注册流程哦"))
            return
        version = _eula_path().stem or "v1"
        community.agree_eula(uid, version)
        self._seed_default_pack(uid)
        _SESSIONS.pop(uid, None)
        self.publish_event("register.completed")
        self._send(text("太好了！感谢你的理解，那我先帮你登记*写写*"))
        self._pause()
        self._send(text("完成啦，已经开放基础功能权限，更多功能会逐步开发中，用“/菜单”指令看看现在有什么吧~"))
