"""DND 5E 升级向导 API 回归：可升级判定、HP 增长、ASI 校验与等级上限。

独立进程运行: python test/scripts/check_trpg_levelup_api.py
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_levelup_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "trpg_chars": os.path.join(_tmp, "trpg_chars")},
)

from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "12345602"
H = {"Authorization": f"Bearer {make_login_key(ME)}"}
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok  ' if ok else 'FAIL'} - {name}" + (f"  {extra}" if extra and not ok else ""))
    if not ok:
        fail += 1


client = TestClient(app)

CARD = {
    "rules": "dnd5e",
    "attributes_mode": "manual",
    "char_name": "艾伦",
    "race": "人类",
    "class_name": "战士",
    "level": 1,
    "xp": 300,
    "str_score": 15, "dex_score": 14, "con_score": 14,
    "int_score": 10, "wis_score": 10, "cha_score": 8,
    "hp": 12, "current_hp": 12,
    "proficient_skills": ["运动", "威吓"],
    "saving_profs": ["力量", "体质"],
}

r = client.post("/api/me/characters", headers=H, json=CARD)
check("建卡 200", r.status_code == 200, r.text[:200])
char_id = r.json()["id"]
check("可升级标记", r.json()["can_level_up"] is True, str(r.json().get("can_level_up")))

r = client.post(f"/api/me/characters/{char_id}/levelup", headers=H,
                json={"hp_mode": "average", "asi": {}, "features": "动作如潮"})
body = r.json()
check("取均值升级 200", r.status_code == 200, r.text[:200])
check("等级 1→2", body.get("level") == 2, str(body.get("level")))
check("HP 12→20", body.get("hp") == 20 and body.get("hp_gain") == 8,
      f"{body.get('hp')}/{body.get('hp_gain')}")
check("当前 HP 同步", body.get("current_hp") == 20, str(body.get("current_hp")))
check("特性追加", "动作如潮" in (body.get("features") or ""), str(body.get("features")))
check("升级后不可再升", body.get("can_level_up") is False, str(body.get("can_level_up")))

r = client.post(f"/api/me/characters/{char_id}/levelup", headers=H,
                json={"hp_mode": "average"})
check("XP 不足 400", r.status_code == 400 and "经验值不足" in r.text, r.text[:160])

# 3 级卡 → 4 级需要 ASI
asi_card = dict(CARD, level=3, xp=2700, hp=28, current_hp=28)
r = client.post("/api/me/characters", headers=H, json=asi_card)
asi_id = r.json()["id"]
r = client.post(f"/api/me/characters/{asi_id}/levelup", headers=H,
                json={"hp_mode": "average", "asi": {}})
check("缺 ASI 400", r.status_code == 400 and "属性值提升" in r.text, r.text[:160])

r = client.post(f"/api/me/characters/{asi_id}/levelup", headers=H,
                json={"hp_mode": "roll", "asi": {"str": 1, "dex": 1}})
body = r.json()
check("掷骰 + 两项各 +1 200", r.status_code == 200, r.text[:200])
check("掷骰结果在范围内", 1 <= body.get("hp_gain", 0) <= 12, str(body.get("hp_gain")))
check("力量 +1", body.get("str_score") == 16, str(body.get("str_score")))
check("等级到 4", body.get("level") == 4, str(body.get("level")))

r = client.post(f"/api/me/characters/{asi_id}/levelup", headers=H,
                json={"hp_mode": "average", "asi": {"str": 2}})
check("超上限 400", r.status_code == 400, r.text[:160])

max_card = dict(CARD, level=20, xp=999999)
r = client.post("/api/me/characters", headers=H, json=max_card)
max_id = r.json()["id"]
r = client.post(f"/api/me/characters/{max_id}/levelup", headers=H, json={"hp_mode": "average"})
check("满级 400", r.status_code == 400 and "20 级" in r.text, r.text[:160])

coc_card = {
    "rules": "coc7th", "char_name": "田宫", "occupation": "药剂师", "age": 28,
    "credit_rating": 40, "luck": 50,
    "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
    "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
    "skills": {"侦查": {"base": 25}},
}
r = client.post("/api/me/characters", headers=H, json=coc_card)
coc_id = r.json()["id"]
r = client.post(f"/api/me/characters/{coc_id}/levelup", headers=H, json={"hp_mode": "average"})
check("COC 卡 400", r.status_code == 400 and "DND 5E" in r.text, r.text[:160])

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
