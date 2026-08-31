"""身份常量接线：base/context 的旧名字来自 config.yaml，且保持可 patch 的模块属性。

子进程验证：换一份特征值配置后全新 import，base/context 应带上特征值——
源码字面量不可能给出特征值，故可区分「真接线」与「碰巧同值」。
进程内 config 可能被其他测试 importlib.reload（重绑定新对象），故不 assertIs。
不 import main（其 import 副作用会写真实 data.db，隔离铁律）。
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_PROBE_CONFIG = """\
bot:
  qq: "999888777"
  nickname: 接线哨兵bot
  super_users: [42, 43]
  default_group: 424242
  ws_url: ws://127.0.0.1:3999
  ws_token: "probe-token"
  llonebot_data_path: /probe/llonebot
  python_data_path: /probe/server_data
onebot:
  http_url: http://127.0.0.1:1
  token: "1"
auth:
  salt: probe-salt
timeline:
  url: http://127.0.0.1:1
  token: probe-timeline
"""

_PROBE_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
from core import base, context, config
assert base.BOT_QQ == "999888777", base.BOT_QQ
assert isinstance(base.BOT_QQ, str)
assert base.NICKNAME == "接线哨兵bot", base.NICKNAME
assert base.SUPER_USER == [42, 43], base.SUPER_USER
assert context.DEFAULT_GROUP_ID == 424242, context.DEFAULT_GROUP_ID
assert context.llonebot_data_path == "/probe/llonebot", context.llonebot_data_path
assert context.python_data_path == "/probe/server_data", context.python_data_path
assert config.WS_TOKEN == "probe-token" and isinstance(config.WS_TOKEN, str)
print("wiring-ok")
"""


class TestWiring(unittest.TestCase):
    def test_identity_wired_via_fresh_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text(_PROBE_CONFIG, encoding="utf-8")
            env = dict(os.environ, BOTERO_CONFIG=str(cfg))
            proc = subprocess.run(
                [sys.executable, "-c", _PROBE_SCRIPT.format(root=str(PROJECT_ROOT))],
                env=env, capture_output=True, text=True, timeout=120,
            )
            self.assertIn(
                "wiring-ok", proc.stdout,
                f"probe 未通过 rc={proc.returncode}\nstderr:\n{proc.stderr}",
            )

    def test_context_attrs_patchable(self):
        # 模块属性可整体替换（测试隔离依赖此性质）
        from core import context
        old = context.python_data_path
        try:
            context.python_data_path = "/tmp/patched"
            self.assertEqual(context.python_data_path, "/tmp/patched")
        finally:
            context.python_data_path = old


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
