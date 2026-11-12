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
check("技能别名表", opts["skill_aliases"].get("侦查") == "侦察", str(opts.get("skill_aliases"))[:80])
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
    "occupation_choices": {"0": ["魅惑"], "1": ["科学:制药"]},
    "skills": {"图书馆使用": {"base": 20, "occupation": 20}, "聆听": {"base": 20, "interest": 10},
               "魅惑": {"base": 15, "occupation": 10}},
    "weapons": [
        {"name": "徒手格斗", "type": "常规武器", "skill": "斗殴", "success": 25, "damage": "1D3+DB",
         "range": "接触", "attacks": "1", "ammo": "", "malfunction": "", "pierce": "×"},
        {"name": ".32 自动手枪", "type": "手枪", "skill": "手枪", "success": 40, "damage": "1D8",
         "range": "15m", "attacks": "1(3)", "ammo": "8", "malfunction": "98", "pierce": "√"},
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
check("技能总数计入", created["skills"]["图书馆使用"]["total"] == 40,
      str(created["skills"].get("图书馆使用")))
check("武器表保留", len(created.get("weapons") or []) == 2 and created["weapons"][1]["name"] == ".32 自动手枪",
      str(created.get("weapons")))
check("武器新字段回传", created["weapons"][0].get("skill") == "斗殴"
      and created["weapons"][1].get("type") == "手枪", str(created["weapons"]))
check("当前 SAN 缺省等于上限", created["current_san"] == 65, str(created.get("current_san")))
check("当前 MP 缺省等于上限", created["current_mp"] == 13, str(created.get("current_mp")))
check("职业点预算", created["occupation_budget"] == 180, str(created.get("occupation_budget")))
check("兴趣点预算", created["interest_budget"] == 170, str(created.get("interest_budget")))

damaged = dict(CARD, current_san=40, current_hp=6)
r = client.post("/api/me/characters", headers=H, json=damaged)
check("当前值原样保存", r.status_code == 200 and r.json()["current_san"] == 40 and r.json()["current_hp"] == 6,
      r.text[:160])

grown = dict(CARD, skills={"图书馆使用": {"base": 20, "growth": 80}})
r = client.post("/api/me/characters", headers=H, json=grown)
check("成长可超过 100%", r.status_code == 200 and any(
    entry["total"] >= 100 for entry in r.json()["skills"].values()), r.text[:160])

unchosen = dict(CARD, skills={"科学:化学": {"base": 1, "occupation": 10}})
r = client.post("/api/me/characters", headers=H, json=unchosen)
check("未选入池即加点 400", r.status_code == 400 and "本职技能" in r.text, r.text[:200])

bad_choice = dict(CARD, occupation_choices={"0": ["攀爬"]})
r = client.post("/api/me/characters", headers=H, json=bad_choice)
check("池外选择 400", r.status_code == 400 and "不在药剂师的可选池" in r.text, r.text[:200])

over_choice = dict(CARD, occupation_choices={"0": ["魅惑", "话术"]})
r = client.post("/api/me/characters", headers=H, json=over_choice)
check("超选 400", r.status_code == 400 and "最多选 1 项" in r.text, r.text[:200])

check("选择已回传", created.get("occupation_choices", {}).get("0") == ["魅惑"], str(created.get("occupation_choices")))

not_own = dict(CARD, skills={"攀爬": {"base": 20, "occupation": 20}})
r = client.post("/api/me/characters", headers=H, json=not_own)
check("非本职技能加点 400", r.status_code == 400 and "本职技能" in r.text, r.text[:200])

bad_skill = dict(CARD, weapons=[{"name": "剑", "skill": "飞天", "damage": "1D8"}])
r = client.post("/api/me/characters", headers=H, json=bad_skill)
check("非法使用技能 400", r.status_code == 400 and "不在技能表里" in r.text, r.text[:200])

no_skill = dict(CARD, weapons=[{"name": "剑", "damage": "1D8"}])
r = client.post("/api/me/characters", headers=H, json=no_skill)
check("缺少使用技能 400", r.status_code == 400 and "缺少使用技能" in r.text, r.text[:200])

bad_weapon = dict(CARD, weapons=[{"name": "剑", "skill": "斗殴", "success": 25, "damage": "一点八"}])
r = client.post("/api/me/characters", headers=H, json=bad_weapon)
check("非法伤害 400", r.status_code == 400 and "不是合法写法" in r.text, r.text[:200])

bad_weapon = dict(CARD, weapons=[{"name": "剑", "damage": "1D8"}, {"name": "剑", "damage": "1D6"}])
r = client.post("/api/me/characters", headers=H, json=bad_weapon)
check("重复武器 400", r.status_code == 400 and "重复添加" in r.text, r.text[:200])

bad = dict(CARD, skills={"图书馆使用": {"base": 25, "occupation": 500}})
r = client.post("/api/me/characters", headers=H, json=bad)
check("职业点超预算 400", r.status_code == 400 and "职业点超出" in r.text, r.text[:160])

bad = dict(CARD, credit_rating=99)
r = client.post("/api/me/characters", headers=H, json=bad)
check("信用评级越界 400", r.status_code == 400 and "信用评级" in r.text, r.text[:160])

bad = dict(CARD, occupation="")
no_occ = dict(CARD, occupation="", occupation_choices={},
              skills={"图书馆使用": {"base": 20}, "聆听": {"base": 20, "interest": 10}})
r = client.post("/api/me/characters", headers=H, json=no_occ)
check("未选职业可保存", r.status_code == 200, r.text[:160])
no_occ_id = r.json().get("id")

occ_points_without_occ = dict(no_occ, skills={"图书馆使用": {"base": 20, "occupation": 10}})
r = client.post("/api/me/characters", headers=H, json=occ_points_without_occ)
check("无职业不能加职业点", r.status_code == 400 and "不能分配职业点" in r.text, r.text[:160])

defaults_view = client.get(f"/api/characters/{ME}/{no_occ_id}", headers=H).json()
skills_view = defaults_view.get("skills") or {}
check("默认技能进接口", skills_view.get("急救", {}).get("total") == 30
      and skills_view.get("闪避", {}).get("base") == (CARD["dex_score"] // 2)
      and len(skills_view) >= 39,
      str({k: v.get("total") for k, v in list(skills_view.items())[:3]}))

# 查看页依赖公共卡片接口返回派生值，COC 卡缺这些字段会整页显示 0
public = client.get(f"/api/characters/{ME}/{created['id']}", headers=H)
view = public.json()
check("查看页拿到 COC 派生值",
      public.status_code == 200 and view.get("rules") == "coc7th"
      and isinstance(view.get("scores"), dict) and view["scores"].get("力量") == 60
      and "skills" in view and "weapons" in view,
      str({k: view.get(k) for k in ("rules", "scores")})[:160])
check("查看页武器含新字段",
      (view.get("weapons") or [{}])[0].get("skill") == "斗殴"
      and (view.get("weapons") or [{}])[0].get("type") == "常规武器",
      str((view.get("weapons") or [{}])[0])[:160])

ref = client.get("/api/trpg/coc/asset-reference?currency=JPY&credit=30", headers=H).json()
check("资产参考值查询", ref.get("level") == "标准" and ref.get("cash") == 120000
      and ref.get("other") == 4500000, str(ref))
bad_ref = client.get("/api/trpg/coc/asset-reference?currency=XXX&credit=30", headers=H)
check("未知币种 400", bad_ref.status_code == 400, str(bad_ref.status_code))

with_assets = dict(CARD, assets={"currency": "JPY", "living_standard": "标准", "cash": "120000",
                                "spending_level": "25000", "other_assets": "都市公寓",
                                "vehicle": "300000", "residence": "0", "luxury": "0",
                                "securities": "0", "other": "0", "remaining": "420000"})
r = client.post("/api/me/characters", headers=H, json=with_assets)
check("资产栏可保存", r.status_code == 200, r.text[:200])
saved_assets = (r.json() or {}).get("assets") or {}
check("资产新字段回传", saved_assets.get("currency") == "JPY"
      and saved_assets.get("vehicle") == "300000"
      and saved_assets.get("other_assets") == "都市公寓", str(saved_assets)[:200])

bad_assets = dict(CARD, assets={"currency": "XXX"})
r = client.post("/api/me/characters", headers=H, json=bad_assets)
check("未知币种 400", r.status_code == 400 and "未知币种" in r.text, r.text[:160])
bad_level = dict(CARD, assets={"living_standard": "贫穷"})
r = client.post("/api/me/characters", headers=H, json=bad_level)
check("非法生活水平 400", r.status_code == 400 and "不在 6 档" in r.text, r.text[:160])

with_items = dict(CARD, inventory=[
    {"status": "装备", "slot": "躯干", "name": "防弹背心", "slots": 2},
    {"status": "携带", "name": "短管霰弹枪", "slots": "3"},
])
r = client.post("/api/me/characters", headers=H, json=with_items)
check("随身物品可保存", r.status_code == 200, r.text[:200])
saved_items = (r.json() or {}).get("inventory") or []
check("随身物品回传", [i.get("name") for i in saved_items] == ["防弹背心", "短管霰弹枪"]
      and saved_items[0].get("status") == "装备", str(saved_items)[:200])

bad_item = dict(CARD, inventory=[{"name": "手电", "status": "乱填"}])
r = client.post("/api/me/characters", headers=H, json=bad_item)
check("非法物品状态 400", r.status_code == 400 and "不在 装备/携带/背包" in r.text, r.text[:160])

opts = client.get("/api/trpg/coc/options", headers=H).json()
library = opts.get("weapon_library") or []
check("武器库随选项下发", len(library) >= 100, str(len(library)))
base_map = opts.get("skill_base") or {}
check("基础值表含三类技能",
      base_map.get("会计") == 5 and base_map.get("科学:化学") == 1 and base_map.get("斗殴") == 25,
      str({k: base_map.get(k) for k in ("会计", "科学:化学", "斗殴")}))
dyn = opts.get("dynamic_bases") or {}
check("动态基础值规则随选项下发",
      dyn.get("闪避", {}).get("divisor") == 2 and dyn.get("母语", {}).get("attr") == "edu_score",
      str(dyn))
check("播种名单只含标准技能",
      len(opts.get("default_skills") or []) == 39
      and "科学:化学" not in (opts.get("default_skills") or []),
      str(len(opts.get("default_skills") or [])))

notes = opts.get("skill_notes") or {}
check("技能说明随选项下发", len(notes) >= 100 and notes.get("会计", {}).get("base") == "5%"
      and notes.get("技艺:表演"), str(len(notes)))
notes_api = client.get("/api/trpg/coc/skill-notes", headers=H).json()
check("技能说明接口", len(notes_api.get("notes") or {}) == len(notes), str(len(notes_api.get("notes") or {})))
occ_entry = next((o for o in (opts.get("occupations") or []) if o.get("name") == "会计师"), {})
check("职业带介绍与关系人", "会计师可能在企业工作" in (occ_entry.get("description") or "")
      and "生意伙伴" in (occ_entry.get("contacts") or ""), str(occ_entry)[:200])
check("物品状态随选项下发", list(opts.get("inventory_statuses") or []) == ["装备", "携带", "背包"],
      str(opts.get("inventory_statuses")))
check("币种与档位随选项下发",
      len(opts.get("currencies") or []) == 6 and len(opts.get("living_levels") or []) == 6
      and len(opts.get("asset_items") or []) == 5,
      str((len(opts.get("currencies") or []), len(opts.get("living_levels") or []))))
check("武器库字段齐全",
      all(k in library[0] for k in ("name", "type", "skill", "damage", "range", "attacks",
                                    "capacity", "malfunction", "pierce", "era")),
      str(library[0])[:160])
check("武器库含时代标记", {w["era"] for w in library} >= {"1920s", "现代"}, str({w["era"] for w in library}))

r = client.get("/api/me/characters", headers=H)
check("列表含 COC 卡", any(c["rules"] == "coc7th" for c in r.json()["characters"]))

updated = dict(CARD, str_score=85, siz_score=70,
               skills={"图书馆使用": {"base": 20, "occupation": 20}},
               weapons=[{"name": "短棍", "type": "常规武器", "skill": "斗殴", "success": 35,
                         "damage": "1D6+DB", "range": "接触"}])
r = client.put(f"/api/me/characters/{created['id']}", headers=H, json=updated)
check("更新 200", r.status_code == 200, r.text[:200])
check("更新后伤害加值变化", r.json()["db"] == "+1D4", str(r.json().get("db")))
check("更新后 HP 变化", r.json()["hp"] == 12, str(r.json().get("hp")))
check("更新后武器表替换", [w["name"] for w in r.json().get("weapons") or []] == ["短棍"],
      str(r.json().get("weapons")))

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
