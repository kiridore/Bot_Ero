"""DND 5E 建卡校验 API 回归：属性生成方式、购点预算、技能限制与规则数据。

独立进程运行: python test/scripts/check_trpg_dnd_builder.py
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_dnd_api_")
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

from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "12345601"
H = {"Authorization": f"Bearer {make_login_key(ME)}"}
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok  ' if ok else 'FAIL'} - {name}" + (f"  {extra}" if extra and not ok else ""))
    if not ok:
        fail += 1


client = TestClient(app)

r = client.get("/api/trpg/rules", headers=H)
rules = r.json()
check("规则接口含生成方式", "point_buy" in rules.get("attribute_modes", {}))
check("战士可选技能范围", rules["classes"]["战士"]["skills"][:2] == ["杂技", "驯兽"])
check("吟游诗人任意技能", rules["classes"]["吟游诗人"]["skills"] == "any")

CARD = {
    "rules": "dnd5e",
    "attributes_mode": "point_buy",
    "char_name": "艾伦",
    "race": "人类",
    "class_name": "战士",
    "level": 1,
    "str_score": 15, "dex_score": 14, "con_score": 14,
    "int_score": 10, "wis_score": 10, "cha_score": 8,
    "proficient_skills": ["运动", "威吓"],
    "saving_profs": ["力量", "体质"],
}

r = client.post("/api/me/characters", headers=H, json=CARD)
check("合法卡 200", r.status_code == 200, r.text[:200])
created = r.json()
check("生成方式入库", created.get("scores", {}).get("str_score") == 16,
      str(created.get("scores")))  # 15 + 人类 +1

bad = dict(CARD, str_score=15, dex_score=15, con_score=15, int_score=15, wis_score=15, cha_score=15)
r = client.post("/api/me/characters", headers=H, json=bad)
check("购点超支 400", r.status_code == 400 and "购点超出预算" in r.text, r.text[:160])

bad = dict(CARD, proficient_skills=["运动", "威吓", "察觉"])
r = client.post("/api/me/characters", headers=H, json=bad)
check("技能超选 400", r.status_code == 400 and "最多选 2 项" in r.text, r.text[:160])

bad = dict(CARD, proficient_skills=["奥术"])
r = client.post("/api/me/characters", headers=H, json=bad)
check("越界技能 400", r.status_code == 400 and "不可选技能" in r.text, r.text[:160])

bad = dict(CARD, str_score=3)
r = client.post("/api/me/characters", headers=H, json=bad)
check("购点范围 400", r.status_code == 400 and "购点值需在 8-15" in r.text, r.text[:160])

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
