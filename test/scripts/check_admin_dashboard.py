"""管理仪表盘 API：超管守卫、插件启停、配置校验/备份/原子写。

独立进程运行: python test/scripts/check_admin_dashboard.py
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_admin_test_")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_tmp)

from fastapi.testclient import TestClient  # noqa: E402
from core import config  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
DB = str(config.DB_PATH)
conn = sqlite3.connect(DB)
from core.database_manager import init_schema  # noqa: E402

init_schema(conn, conn.cursor())
conn.commit()
conn.close()
SH = {"Authorization": "Bearer " + make_login_key(str(config.SUPER_USER[0]))}
JH = {"Content-Type": "application/json", **SH}
OH = {"Authorization": "Bearer " + make_login_key("999")}

def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1

fail = 0

# —— 超管守卫 ——
for method, path in [("get", "/api/admin/plugins/scopes"), ("get", "/api/admin/plugins?group_id=0"),
                     ("get", "/api/admin/config")]:
    r = getattr(client, method)(path, headers=OH)
    check(f"非超管 {path.split('?')[0]} 403", r.status_code == 403)
r = client.put("/api/admin/plugins", headers={"Content-Type": "application/json", **OH},
               json={"group_id": 0, "plugin_key": "dice", "enabled": True})
check("非超管 PUT 插件 403", r.status_code == 403)
r = client.put("/api/admin/config", headers={"Content-Type": "application/json", **OH}, json={"yaml": "x: 1"})
check("非超管 PUT 配置 403", r.status_code == 403)

# —— 范围与插件列表 ——
r = client.get("/api/admin/plugins/scopes", headers=SH)
scopes = r.json().get("scopes", [])
check("scopes 200 含私聊", r.status_code == 200 and any(s["group_id"] == 0 for s in scopes))
check("scopes 含默认群且标注", any(s["group_id"] == config.DEFAULT_GROUP_ID and s["is_default"] for s in scopes))

r = client.get(f"/api/admin/plugins?group_id={config.DEFAULT_GROUP_ID}", headers=SH)
data = r.json()
check("插件列表 200 且非空", r.status_code == 200 and len(data.get("plugins", [])) > 0)
system_keys = {p["key"] for p in data.get("plugins", []) if p["system"]}
check("系统插件被标记", len(system_keys) > 0 and "menu" in system_keys)
check("列表含常规插件", any(p["key"] == "dice" and not p["system"] for p in data.get("plugins", [])))

# —— toggle ——
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "dice", "enabled": False})
check("禁用写库", r.status_code == 200)
c = sqlite3.connect(DB)
row = c.execute("SELECT 1 FROM group_plugin_config WHERE group_id=777 AND plugin_name='dice'").fetchone()
c.close()
check("禁用=删行", row is None)
r = client.get("/api/admin/plugins?group_id=777", headers=SH)
dice_row = next((p for p in r.json().get("plugins", []) if p["key"] == "dice"), None)
check("禁用后列表反映", dice_row is not None and dice_row["enabled"] is False)
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "dice", "enabled": True})
c = sqlite3.connect(DB)
row = c.execute("SELECT 1 FROM group_plugin_config WHERE group_id=777 AND plugin_name='dice'").fetchone()
c.close()
check("启用=有行", row is not None)
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "menu", "enabled": False})
check("系统插件 400", r.status_code == 400)
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "no_such_plugin", "enabled": True})
check("未知插件 400", r.status_code == 400)

# —— 配置读取与校验写 ——
r = client.get("/api/admin/config", headers=SH)
orig = open(config.CONFIG_PATH, encoding="utf-8").read()
check("config GET 与磁盘一致", r.status_code == 200 and r.json()["yaml"] == orig)

bad_cases = [
    ("坏缩进", "bot: [unclosed"),
    ("非 dict 顶层", "- a\n- b"),
    ("缺必填", "bot:\n  qq: \"1\"\n"),
]
for name, payload in bad_cases:
    r = client.put("/api/admin/config", headers=JH, json={"yaml": payload})
    unchanged = open(config.CONFIG_PATH, encoding="utf-8").read() == orig
    check(f"非法配置 400 且不落盘（{name}）", r.status_code == 400 and unchanged, r.text[:80])

valid = orig + "\n# web edit test marker\n"
r = client.put("/api/admin/config", headers=JH, json={"yaml": valid})
bak = Path(str(config.CONFIG_PATH) + ".bak")
check("合法保存 200", r.status_code == 200, r.text[:80])
check("文件已更新", open(config.CONFIG_PATH, encoding="utf-8").read() == valid)
check("备份生成且为旧内容", bak.is_file() and bak.read_text(encoding="utf-8") == orig)
r = client.get("/api/admin/config", headers=SH)
check("保存后回读一致", r.json().get("yaml") == valid)

print(f"\n{'ALL PASS' if fail == 0 else f'{fail} FAILED'}")
sys.exit(1 if fail else 0)
