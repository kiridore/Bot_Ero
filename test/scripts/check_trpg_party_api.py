"""跑团准备名单 Web API 回归：准备中列表、成员口径、DM 审核角色卡权限。

独立进程运行: python test/scripts/check_trpg_party_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_trpg_party_api_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "images": os.path.join(_tmp, "record_images")},
    thumbs={"cache_dir": os.path.join(_tmp, "thumb_cache")},
)

from core import config  # noqa: E402
from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core import character_store as char_store  # noqa: E402
from core import user_settings as user_settings  # noqa: E402
from core.trpg import party  # noqa: E402
from webapp.app import app  # noqa: E402

DM = "12345601"
PLAYER = "12345602"
STRANGER = "12345603"
GROUP = "296470819"
client = TestClient(app)
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def auth(uid: str) -> dict:
    return {"Authorization": "Bearer " + make_login_key(int(uid))}


def make_card(user_id: str, name: str) -> int:
    char_id = char_store.create_char(user_id, {
        "rules": "coc7th", "char_name": name, "occupation": "药剂师",
        "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
        "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
    })
    char_store.set_current(user_id, char_id)
    return char_id


# ── 准备中：DM + 一名已准备玩家 + 一名观察者 ─────────────
dm_card = make_card(DM, "守密人")
player_card = make_card(PLAYER, "田宫真莉")
party.set_role(GROUP, DM, "dm", nickname="守密人")
party.set_role(GROUP, PLAYER, "ob")
party.set_role(GROUP, "12345699", "ob")
party.set_prepared(GROUP, PLAYER, {
    "user_id": PLAYER, "nickname": "老张", "char_id": player_card,
    "char_name": "田宫真莉", "prepared_at": "2026-11-12 10:00:00",
})

r = client.get("/api/trpg/parties", headers=auth(DM))
check("准备中列表 200", r.status_code == 200, r.text[:160])
parties = (r.json() or {}).get("parties") or []
first = parties[0] if parties else {}
check("列表含本群", first.get("group_id") == GROUP, str(first.get("group_id")))
check("名单含 DM 与已准备玩家",
      {m["user_id"] for m in first.get("members") or []} >= {DM, PLAYER},
      str([m["user_id"] for m in first.get("members") or []]))
check("已准备计数与人数", first.get("prepared_count") == 1 and first.get("member_count") == 3,
      f"{first.get('prepared_count')}/{first.get('member_count')}")
check("规则名下发", first.get("rules_name") == "DND 5E" or bool(first.get("rules_name")), str(first.get("rules_name")))
check("DM 视角标记 is_dm", first.get("is_dm") is True and first.get("can_audit") is True,
      str((first.get("is_dm"), first.get("can_audit"))))
party.set_group_name(GROUP, "夜航团")
with_name = ((client.get("/api/trpg/parties", headers=auth(DM)).json() or {}).get("parties") or [{}])[0]
check("群名随准备名单下发", with_name.get("group_name") == "夜航团", str(with_name.get("group_name")))

check("DM 昵称回落快照", first.get("dm_name") == "守密人", str(first.get("dm_name")))
check("成员快照昵称保留", any(m["user_id"] == DM and m["nickname"] == "守密人"
                             for m in first.get("members") or []),
      str([m["nickname"] for m in first.get("members") or []]))

r = client.get("/api/trpg/parties", headers=auth(STRANGER))
other = (r.json() or {}).get("parties") or []
check("非 DM 也能看到准备中名单", bool(other) and other[0].get("is_dm") is False,
      str((other[0] if other else {}).get("is_dm")))
check("非 DM 无审核权限", bool(other) and other[0].get("can_audit") is False,
      str((other[0] if other else {}).get("can_audit")))

# 实时名片优先于快照；取不到时回落快照
from unittest.mock import patch as _patch  # noqa: E402
with _patch("webapp.trpg.app.resolve_group_member_name", return_value="实时名片"):
    live = (((client.get("/api/trpg/parties", headers=auth(DM)).json() or {}).get("parties")) or [{}])[0]
check("DM 昵称实时获取", live.get("dm_name") == "实时名片", str(live.get("dm_name")))
with _patch("webapp.trpg.app.resolve_group_member_name", return_value=""):
    fallback = (((client.get("/api/trpg/parties", headers=auth(DM)).json() or {}).get("parties")) or [{}])[0]
check("实时取不到回落快照", fallback.get("dm_name") == "守密人", str(fallback.get("dm_name")))

# 超级用户不是本群 DM 时：不能冒充 DM，但有审核权限
from unittest.mock import patch  # noqa: E402
with patch("webapp.trpg.app.core_config.SUPER_USER", {int(STRANGER)}):
    super_view = (((client.get("/api/trpg/parties", headers=auth(STRANGER)).json() or {})
                   .get("parties")) or [{}])[0]
check("超级用户 is_dm 为假但可审核",
      super_view.get("is_dm") is False and super_view.get("is_super") is True
      and super_view.get("can_audit") is True,
      str((super_view.get("is_dm"), super_view.get("is_super"), super_view.get("can_audit"))))

# ── 角色卡权限 ────────────────────────────────────
r = client.get(f"/api/trpg/party/{GROUP}/card/{PLAYER}", headers=auth(DM))
check("DM 可看参与者卡", r.status_code == 200 and r.json().get("char_name") == "田宫真莉", r.text[:160])

r = client.get(f"/api/trpg/party/{GROUP}/card/{PLAYER}", headers=auth(PLAYER))
check("本人可看自己的卡", r.status_code == 200 and r.json().get("char_name") == "田宫真莉", r.text[:160])

user_settings.update_settings(PLAYER, {"privacy": {"char_public": False}})
r = client.get(f"/api/trpg/party/{GROUP}/card/{PLAYER}", headers=auth(STRANGER))
check("私密卡对旁观者 403", r.status_code == 403, r.text[:160])
r = client.get(f"/api/trpg/party/{GROUP}/card/{PLAYER}", headers=auth(DM))
check("私密卡 DM 仍可审核", r.status_code == 200, r.text[:160])

user_settings.update_settings(PLAYER, {"privacy": {"char_public": True}})
r = client.get(f"/api/trpg/party/{GROUP}/card/{PLAYER}", headers=auth(STRANGER))
check("公开卡旁观者可看", r.status_code == 200, r.text[:160])

r = client.get(f"/api/trpg/party/{GROUP}/card/{STRANGER}", headers=auth(DM))
check("名单外的人 404", r.status_code == 404, r.text[:160])

r = client.get("/api/trpg/party/999999999/card/" + PLAYER, headers=auth(DM))
check("没有准备的群 404", r.status_code == 404, r.text[:160])

# ── 没有 DM 的群不出现在列表 ──────────────────────
party.set_role(GROUP, DM, "ob")  # 撤掉 DM（设成观察者）
r = client.get("/api/trpg/parties", headers=auth(DM))
check("没有 DM 时不列为准备中", ((r.json() or {}).get("parties") or []) == [], r.text[:160])

print("\n全部通过" if fail == 0 else f"\n{fail} 项失败")
sys.exit(0 if fail == 0 else 1)
