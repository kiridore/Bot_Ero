"""COC 7th 建卡 API 回归：选项数据、建卡校验、派生值与更新。

独立进程运行: python test/scripts/check_trpg_coc_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_coc_api_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={
        "db": _db,
        "images": os.path.join(_tmp, "record_images"),
        "trpg_chars": os.path.join(_tmp, "trpg_chars"),
        "user_settings": os.path.join(_tmp, "user_settings"),
    },
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
from webapp.app import app  # noqa: E402

ME = "12345601"
KEY = make_login_key(ME)
H = {"Authorization": f"Bearer {KEY}"}
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok  ' if ok else 'FAIL'} - {name}" + (f"  {extra}" if extra and not ok else ""))
    if not ok:
        fail += 1


client = TestClient(app)

# —— 建卡数据源 ——
r = client.get("/api/trpg/coc/options", headers=H)
check("选项接口 200", r.status_code == 200, str(r.status_code))
opts = r.json()
check("职业模板齐全", len(opts["occupations"]) > 50, str(len(opts["occupations"])))
check("技能基础值含侦察", opts["skill_base"].get("侦察") == 25)
check("技能类别存在", "技艺" in opts["skill_categories"])
occ = next(o for o in opts["occupations"] if o["name"] == "药剂师")
check("职业含信誉区间与公式", occ["credit_min"] == 35 and occ["credit_max"] == 75 and "教育" in occ["formula"])

CARD = {
    "rules": "coc7th",
    "char_name": "田宫真莉",
    "occupation": "药剂师",
    "age": 28,
    "sex": "女",
    "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
    "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
    "luck": 50, "credit_rating": 40, "cthulhu_mythos": 0,
    "skills": {"侦查": {"base": 25, "occupation": 20}, "聆听": {"base": 20, "interest": 10}},
    "weapons": [
        {"name": "徒手格斗", "success": 25, "damage": "1D3+DB", "range": "—",
         "attacks": "1", "ammo": "—", "malfunction": "—", "pierce": "—"},
        {"name": ".32 自动手枪", "success": 40, "damage": "1D8", "range": "15m",
         "attacks": "1(3)", "ammo": "8", "malfunction": "98", "pierce": "—"},
    ],
    "assets": {"cash": "40", "spending_level": "普通", "living_standard": "小康"},
    "social_background": {"traits": "好奇心旺盛"},
    "notes": "",
}

r = client.post("/api/me/characters", headers=H, json=CARD)
check("建卡 200", r.status_code == 200, r.text[:200])
created = r.json()
check("规则保留", created["rules"] == "coc7th")
check("HP 派生", created["hp"] == 10, str(created.get("hp")))
check("MP 派生", created["mp"] == 13, str(created.get("mp")))
check("MOV 派生", created["mov"] == 9, str(created.get("mov")))
check("闪避派生", created["dodge"] == 27, str(created.get("dodge")))
check("技能总数计入", created["skills"]["侦查"]["total"] == 45, str(created["skills"].get("侦查")))
check("武器表保留", len(created.get("weapons") or []) == 2 and created["weapons"][1]["name"] == ".32 自动手枪",
      str(created.get("weapons")))
check("当前 SAN 缺省等于上限", created["current_san"] == 65, str(created.get("current_san")))
check("当前 MP 缺省等于上限", created["current_mp"] == 13, str(created.get("current_mp")))
check("职业点预算", created["occupation_budget"] == 180, str(created.get("occupation_budget")))
check("兴趣点预算", created["interest_budget"] == 170, str(created.get("interest_budget")))

damaged = dict(CARD, current_san=40, current_hp=6)
r = client.post("/api/me/characters", headers=H, json=damaged)
check("当前值原样保存", r.status_code == 200 and r.json()["current_san"] == 40 and r.json()["current_hp"] == 6,
      r.text[:160])

bad = dict(CARD, skills={"侦查": {"base": 25, "occupation": 500}})
r = client.post("/api/me/characters", headers=H, json=bad)
check("职业点超预算 400", r.status_code == 400 and "职业点超出" in r.text, r.text[:160])

bad = dict(CARD, credit_rating=99)
r = client.post("/api/me/characters", headers=H, json=bad)
check("信用评级越界 400", r.status_code == 400 and "信用评级" in r.text, r.text[:160])

bad = dict(CARD, occupation="")
r = client.post("/api/me/characters", headers=H, json=bad)
check("未选职业 400", r.status_code == 400 and "职业" in r.text, r.text[:160])

r = client.get("/api/me/characters", headers=H)
check("列表含 COC 卡", any(c["rules"] == "coc7th" for c in r.json()["characters"]))

updated = dict(CARD, str_score=85, siz_score=70,
               skills={"侦查": {"base": 25, "occupation": 20}},
               weapons=[{"name": "短棍", "success": 35, "damage": "1D6+DB"}])
r = client.put(f"/api/me/characters/{created['id']}", headers=H, json=updated)
check("更新 200", r.status_code == 200, r.text[:200])
check("更新后伤害加值变化", r.json()["db"] == "+1D4", str(r.json().get("db")))
check("更新后 HP 变化", r.json()["hp"] == 12, str(r.json().get("hp")))
check("更新后武器表替换", [w["name"] for w in r.json().get("weapons") or []] == ["短棍"],
      str(r.json().get("weapons")))

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
