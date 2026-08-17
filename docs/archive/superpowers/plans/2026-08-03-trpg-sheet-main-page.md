# 5E 角色卡第 1 页主卡面扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 5E 官方角色卡（2014 版中译）第 1 页主卡面的全部条目扩展进现有网页端车卡编辑器/查看页，补齐豁免、熟练加值、先攻/速度、生命骰、死亡豁免、装备钱币、攻击与法术、特性与特质、背景四要素等字段。

**Architecture:** 沿用纯 JSON 存储（`core/character_store`，无 schema 变更——字段即 dict 键）。派生计算（熟练加值/豁免加值/被动感知/先攻/生命骰）扩展进 `core/trpg/character.py` 的 `finalize()`，前端 `trpg.js` 的 `computeSheet()` 保持同口径；`CharacterIn`/`CharOut` 透传新字段。骰子引用契约（`resolve_expression_values`）不变。

**Tech Stack:** Python stdlib、FastAPI（`checkin_gallery/app.py`）、vanilla JS（`checkin_gallery/static/trpg.js` / `char_view.js`）。

## Global Constraints

- **派生字段不入盘**：`prof_bonus`/`save_mods`/`passive_perception`/`initiative`/`hit_dice` 只由 `finalize()` 计算返回，不写入 JSON 文件；存盘的是原始字段（`saving_profs`/`current_hp`/`speed`/`death_saves_*`/`inspiration`/`attacks` 等）。
- **标准键契约不变**：6 属性键 `str_score`..`cha_score`、技能名（中文）、`proficient_skills`、`char_name`/`race`/`class_name`/`level`/`hp`/`ac`/`notes`/`background` 必须保留——骰子与旧数据依赖。
- **旧角色兼容**：所有新增字段读侧默认兜底（`char_data.get(k, 默认)`），缺失不报错。
- **前后端口径一致**：熟练加值 `2 + (level-1)//4`；豁免加值 = 属性加值 + (豁免熟练 ? 熟练加值 : 0)；被动感知 `10 + 感知加值 + (察觉熟练 ? 2 : 0)`；先攻 = 敏捷加值；生命骰 = `{level}d{职业hp骰}`。
- **attacks 存储格式**：`list[str]`，每行一条 `名称|攻击加值|伤害`（与 equipment 同为逐行字符串 list）。
- 无 async/await、无 f-string SQL、无框架；中文 Conventional Commits。
- 测试：`python3 test/<name>.py`。
- 同步维护（同 commit）：`specs/web-gallery.md`、`KNOWLEDGE_BASE.md`。

---

### Task 1: `finalize()` 扩展派生计算 + 单测

**Files:**
- Modify: `core/trpg/character.py`
- Modify: `plugins/trpg_char/character.py`（re-export，通常无需改——仅当导出名变化时）
- Create: `test/test_trpg_finalize.py`

**Interfaces:**
- Consumes: 无（已有 `ATTRIBUTES`/`SKILLS`/`ability_modifier`/`class_info`）
- Produces: `finalize(char_data)` 输出新增键：`prof_bonus: int`、`save_mods: dict`（键=6 中文属性名，值=含熟练加值）、`passive_perception: int`、`initiative: int`、`hit_dice: str`（如 `"1d8"`）
- 输入新增键：`saving_profs: list[str]`（6 中文属性名子集）、`level: int`（已有）

- [ ] **Step 1: 写失败测试 `test/test_trpg_finalize.py`**

```python
"""测试 core.trpg.character.finalize 的 5E 派生计算扩展。

运行: python3 test/test_trpg_finalize.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg.character import finalize


def _base(**kw) -> dict:
    data = {
        "char_name": "艾伦", "race": "人类", "class_name": "法师", "level": 1,
        "str_score": 15, "dex_score": 14, "con_score": 13,
        "int_score": 12, "wis_score": 10, "cha_score": 8,
        "proficient_skills": [], "hp": 0, "ac": 0,
    }
    data.update(kw)
    return data


class TestProficiencyBonus(unittest.TestCase):
    def test_level1_is_2(self):
        self.assertEqual(finalize(_base(level=1))["prof_bonus"], 2)

    def test_level5_is_3(self):
        self.assertEqual(finalize(_base(level=5))["prof_bonus"], 3)

    def test_level9_is_4(self):
        self.assertEqual(finalize(_base(level=9))["prof_bonus"], 4)

    def test_level17_is_6(self):
        self.assertEqual(finalize(_base(level=17))["prof_bonus"], 6)


class TestSavingThrows(unittest.TestCase):
    # 人类 +1 全属性；str 15+1=16 → 加值 +3；dex 14+1=15 → +2
    def test_no_prof_is_ability_mod(self):
        data = finalize(_base())
        self.assertEqual(data["save_mods"]["力量"], 3)
        self.assertEqual(data["save_mods"]["敏捷"], 2)

    def test_prof_adds_proficiency(self):
        data = finalize(_base(saving_profs=["力量"]))
        self.assertEqual(data["save_mods"]["力量"], 3 + 2)
        self.assertEqual(data["save_mods"]["敏捷"], 2)

    def test_missing_saving_profs_defaults_empty(self):
        data = finalize(_base())
        self.assertEqual(data["save_mods"]["魅力"], -1)


class TestDerived(unittest.TestCase):
    def test_passive_perception(self):
        data = finalize(_base(wis_score=14))  # 人类 +1 → 15 → +2
        self.assertEqual(data["passive_perception"], 12)

    def test_passive_perception_with_proficiency(self):
        data = finalize(_base(wis_score=14, proficient_skills=["察觉"]))
        self.assertEqual(data["passive_perception"], 14)

    def test_initiative_is_dex_mod(self):
        data = finalize(_base())
        self.assertEqual(data["initiative"], 2)

    def test_hit_dice_uses_class_die(self):
        data = finalize(_base(class_name="法师"))  # d6
        self.assertEqual(data["hit_dice"], "1d6")
        data = finalize(_base(class_name="野蛮人", level=3))  # d12
        self.assertEqual(data["hit_dice"], "3d12")

    def test_old_data_without_new_keys(self):
        data = finalize(_base())
        for key in ("prof_bonus", "save_mods", "passive_perception", "initiative", "hit_dice"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 test/test_trpg_finalize.py`
Expected: FAIL（`finalize` 输出无 `prof_bonus` 等键，KeyError/AssertionError）

- [ ] **Step 3: 扩展 `core/trpg/character.py` 的 `finalize`**

在现有 `finalize` 中按下列位置插入（保持既有逻辑不变）：

```python
    con_mod = ability_modifier(scores["con_score"])
    dex_mod = ability_modifier(scores["dex_score"])

    cls = class_info(char_data.get("class_name", ""))
    hp_die = cls.get("hp_die", 8)
    out["hp"] = hp_die + con_mod if char_data.get("hp") in (None, 0) else int(char_data["hp"])
    out["ac"] = 10 + dex_mod if char_data.get("ac") in (None, 0) else int(char_data["ac"])

    level = int(char_data.get("level", 1))
    out["prof_bonus"] = 2 + (level - 1) // 4

    saving_profs = set(char_data.get("saving_profs", []) or [])
    save_mods = {}
    for attr in ATTRIBUTES:
        mod = ability_modifier(scores[_attr_key(attr)])
        if attr in saving_profs:
            mod += out["prof_bonus"]
        save_mods[attr] = mod
    out["save_mods"] = save_mods
```

然后在技能段之后追加：

```python
    out["skill_mods"] = skill_mods

    wis_mod = ability_modifier(scores["wis_score"])
    perception_bonus = 2 if "察觉" in proficient else 0
    out["passive_perception"] = 10 + wis_mod + perception_bonus
    out["initiative"] = dex_mod
    out["hit_dice"] = f"{level}d{hp_die}"

    return out
```

同时更新 `format_sheet`（QQ 端查看受益，在属性行后追加一行）：

```python
    prof_bonus = data.get("prof_bonus", 0)
    init = data.get("initiative", 0)
    passive = data.get("passive_perception", 10)
    hit_dice = data.get("hit_dice", "1d8")
    lines.append(f"熟练加值: +{prof_bonus}    先攻: {init}    被动感知: {passive}    生命骰: {hit_dice}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 test/test_trpg_finalize.py`
Expected: 全部 PASS。再跑回归：`python3 test/test_trpg.py`、`python3 test/test_trpg_char.py`（骰子引用契约未变，应全绿）

- [ ] **Step 5: Commit**

```bash
git add core/trpg/character.py test/test_trpg_finalize.py
git commit -m "feat(跑团): finalize 扩展熟练加值/豁免/被动感知/先攻/生命骰派生计算"
```

---

### Task 2: API 层透传新字段（`checkin_gallery/app.py`）

**Files:**
- Modify: `checkin_gallery/app.py`（`CharacterIn`、`CharOut`、`_char_to_out`）

**Interfaces:**
- Consumes: `core.trpg.character.finalize` 新派生键（Task 1）
- Produces: 前端依赖的字段（Task 3/4）

- [ ] **Step 1: 扩展 `CharacterIn`**

```python
class CharacterIn(BaseModel):
    char_name: str
    race: str
    class_name: str
    level: int = 1
    background: str = ""
    player_name: str = ""
    alignment: str = ""
    xp: int = 0
    str_score: int
    dex_score: int
    con_score: int
    int_score: int
    wis_score: int
    cha_score: int
    proficient_skills: list[str] = []
    saving_profs: list[str] = []
    hp: int = 0
    ac: int = 0
    current_hp: int = 0
    temp_hp: int = 0
    speed: int = 30
    death_saves_success: int = 0
    death_saves_fail: int = 0
    inspiration: bool = False
    equipment: list[str] = []
    other_proficiencies: str = ""
    attacks: list[str] = []
    features: str = ""
    personality_traits: str = ""
    ideals: str = ""
    bonds: str = ""
    flaws: str = ""
    notes: str = ""
```

- [ ] **Step 2: 扩展 `CharOut` 与 `_char_to_out`**

```python
class CharOut(BaseModel):
    id: int
    user_id: str
    display_name: str
    char_name: str
    race: str
    class_name: str
    level: int
    hp: int
    ac: int
    skill_mods: dict
    scores: dict
    prof_bonus: int
    save_mods: dict
    passive_perception: int
    initiative: int
    hit_dice: str
    proficient_skills: list[str]
    notes: str
    background: str
    player_name: str
    alignment: str
    xp: int
    str_score: int
    dex_score: int
    con_score: int
    int_score: int
    wis_score: int
    cha_score: int
    saving_profs: list[str]
    current_hp: int
    temp_hp: int
    speed: int
    death_saves_success: int
    death_saves_fail: int
    inspiration: bool
    equipment: list[str]
    other_proficiencies: str
    attacks: list[str]
    features: str
    personality_traits: str
    ideals: str
    bonds: str
    flaws: str
```

`_char_to_out` 在 `finalized = trpg_char.finalize(data)` 后追加字段（派生取 finalized、原始取 data，带默认兜底）：

```python
    return CharOut(
        ...existing 字段不变...,
        prof_bonus=finalized.get("prof_bonus", 2),
        save_mods=finalized.get("save_mods", {}),
        passive_perception=finalized.get("passive_perception", 10),
        initiative=finalized.get("initiative", 0),
        hit_dice=finalized.get("hit_dice", "1d8"),
        player_name=data.get("player_name", ""),
        alignment=data.get("alignment", ""),
        xp=int(data.get("xp", 0)),
        saving_profs=data.get("saving_profs", []) or [],
        current_hp=int(data.get("current_hp", 0)),
        temp_hp=int(data.get("temp_hp", 0)),
        speed=int(data.get("speed", 30)),
        death_saves_success=int(data.get("death_saves_success", 0)),
        death_saves_fail=int(data.get("death_saves_fail", 0)),
        inspiration=bool(data.get("inspiration", False)),
        equipment=data.get("equipment", []) or [],
        other_proficiencies=data.get("other_proficiencies", ""),
        attacks=data.get("attacks", []) or [],
        features=data.get("features", ""),
        personality_traits=data.get("personality_traits", ""),
        ideals=data.get("ideals", ""),
        bonds=data.get("bonds", ""),
        flaws=data.get("flaws", ""),
    )
```

注意：`equipment` 现有类型 `list` → `list[str]`（旧数据可能存任意 list，pydantic 输出时 list[str] 对非 str 元素会报错——如旧 DB 时代遗留；当前存储已全 JSON 化且新写入均为 str list，风险可忽略；若担心可在 `_char_to_out` 里 `[str(x) for x in data.get("equipment", [])]`）。

- [ ] **Step 3: 冒烟验证**

```bash
python3 -m checkin_gallery & sleep 2
KEY=$(python3 -c "from checkin_gallery.auth import make_login_key; print(make_login_key('123456'))")
curl -s -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8765/api/me/characters \
  -d '{"char_name":"测试","race":"人类","class_name":"战士","level":5,"str_score":15,"dex_score":14,"con_score":13,"int_score":12,"wis_score":10,"cha_score":8,"proficient_skills":["察觉"],"saving_profs":["力量"],"speed":30,"attacks":["长剑|+7|1d8 挥砍"]}' | python3 -m json.tool
kill %1; rm -rf server_data/trpg_chars/123456
```

Expected: 响应含 `prof_bonus: 3`、`save_mods.力量: 5`、`passive_perception: 12`、`initiative: 2`、`hit_dice: "5d10"`、`attacks` 原样回传；清理测试数据。

- [ ] **Step 4: Commit**

```bash
git add checkin_gallery/app.py
git commit -m "feat(网页): 角色 API 透传 5E 主卡面新增字段与派生计算"
```

---

### Task 3: 前端编辑器扩展（`checkin_gallery/static/trpg.js`）

**Files:**
- Modify: `checkin_gallery/static/trpg.js`

**Interfaces:**
- Consumes: Task 1 的派生口径、Task 2 的 API 字段
- Produces: 无（页面）

**改动点（均在 `renderEditor`/`refresh`/`readForm` 内，先读当前文件确认行号）：**

- [ ] **Step 1: 扩展新建种子对象（`renderList` 中 `editing = {...}`）**

```javascript
    editing = {
      char_name: "", race: "人类", class_name: "战士", level: 1, background: "",
      player_name: "", alignment: "", xp: 0,
      str_score: 10, dex_score: 10, con_score: 10, int_score: 10, wis_score: 10, cha_score: 10,
      proficient_skills: [], saving_profs: [],
      hp: 0, ac: 0, current_hp: 0, temp_hp: 0, speed: 30,
      death_saves_success: 0, death_saves_fail: 0, inspiration: false,
      equipment: [], other_proficiencies: "", attacks: [], features: "",
      personality_traits: "", ideals: "", bonds: "", flaws: "",
      notes: "",
    };
```

- [ ] **Step 2: 扩展编辑器表单 HTML（`form.innerHTML`）**

基本信息区追加两行（在 背景 行之后、备注 行之前）：

```html
        <tr><th>玩家名</th><td><input type="text" data-f="player_name"></td>
            <th>阵营</th><td><input type="text" data-f="alignment" placeholder="如：守序善良"></td></tr>
        <tr><th>经验值</th><td><input type="number" data-f="xp" min="0"></td>
            <th>熟练加值</th><td id="profBonusCell"></td></tr>
```

战斗区替换为完整版：

```html
    <section class="settings-section">
      <div class="section-head"><h2>战斗 <span class="muted">（未填 HP/AC 时按规则自动计算）</span></h2></div>
      <table class="trpg-table">
        <tr><th>HP</th><td><input type="number" data-f="hp" min="0"></td>
            <th>AC</th><td><input type="number" data-f="ac" min="0"></td>
            <th>先攻</th><td id="initiativeCell"></td></tr>
        <tr><th>当前 HP</th><td><input type="number" data-f="current_hp" min="0"></td>
            <th>临时 HP</th><td><input type="number" data-f="temp_hp" min="0"></td>
            <th>速度</th><td><input type="number" data-f="speed" min="0"></td></tr>
        <tr><th>生命骰</th><td id="hitDiceCell"></td>
            <th>被动感知</th><td id="passiveCell"></td>
            <th>激励</th><td><input type="checkbox" data-f="inspiration" style="width:auto;height:auto;"></td></tr>
        <tr><th>死亡豁免成功</th><td><input type="number" data-f="death_saves_success" min="0" max="3"></td>
            <th>死亡豁免失败</th><td><input type="number" data-f="death_saves_fail" min="0" max="3"></td>
            <th colspan="2"></th></tr>
        <tr><th>建议 HP</th><td colspan="5" id="hpHint"></td></tr>
      </table>
    </section>
```

在战斗区之后、保存按钮之前插入两个新区块：

```html
    <section class="settings-section">
      <div class="section-head"><h2>资源 <span class="muted">（装备/攻击/特性，每行一条）</span></h2></div>
      <table class="trpg-table">
        <tr><th>装备与钱币</th><td colspan="3"><textarea data-f="equipment" rows="3" placeholder="每行一条，如：长剑、皮甲、50gp"></textarea></td></tr>
        <tr><th>其他熟练项和语言</th><td colspan="3"><textarea data-f="other_proficiencies" rows="2" placeholder="每行一条，如：通用语、精灵语、铁匠工具"></textarea></td></tr>
        <tr><th>攻击与法术</th><td colspan="3"><textarea data-f="attacks" rows="3" placeholder="格式：名称|攻击加值|伤害&#10;如：长剑|+5|1d8 挥砍"></textarea></td></tr>
        <tr><th>特性与特质</th><td colspan="3"><textarea data-f="features" rows="3"></textarea></td></tr>
      </table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>背景 <span class="muted">（角色四要素）</span></h2></div>
      <table class="trpg-table">
        <tr><th>个人特点</th><td colspan="3"><textarea data-f="personality_traits" rows="2"></textarea></td></tr>
        <tr><th>理想</th><td colspan="3"><textarea data-f="ideals" rows="2"></textarea></td></tr>
        <tr><th>牵绊</th><td colspan="3"><textarea data-f="bonds" rows="2"></textarea></td></tr>
        <tr><th>缺点</th><td colspan="3"><textarea data-f="flaws" rows="2"></textarea></td></tr>
      </table>
    </section>
```

- [ ] **Step 3: 扩展 `computeSheet`（`trpg.js` 顶部计算函数区）**

在现有 `computeSheet` 内（`skillMods` 计算之后、`return` 之前）追加：

```javascript
  const profBonus = 2 + Math.floor((Number(data.level || 1) - 1) / 4);
  const savingProfs = data.saving_profs || [];
  const saveMods = {};
  for (const attr of rules.attributes) {
    let m = abilityMod(scores[attrKey(attr)]);
    if (savingProfs.includes(attr)) m += profBonus;
    saveMods[attr] = m;
  }
  const wisMod = abilityMod(scores.wis_score);
  const passivePerception = 10 + wisMod + ((data.proficient_skills || []).includes("察觉") ? 2 : 0);
  return {
    scores, skillMods, saveMods, profBonus,
    passivePerception,
    initiative: abilityMod(scores.dex_score),
    hitDice: `${data.level || 1}d${hpDie}`,
    hp: Number(data.hp) || hpDie + conMod,
    ac: Number(data.ac) || 10 + dexMod,
    hpDie,
  };
```

- [ ] **Step 4: 扩展 `refresh()` 渲染**

属性表行内追加豁免列（在现有 `<td class="muted">加值...</td>` 之后）：

```javascript
      const tdSave = document.createElement("td");
      const saveCb = document.createElement("input");
      saveCb.type = "checkbox";
      saveCb.checked = (data.saving_profs || []).includes(attr);
      saveCb.dataset.saveprof = attr;
      saveCb.title = "豁免熟练";
      tdSave.appendChild(saveCb);
      tr.appendChild(tdSave);
      const tdSaveMod = document.createElement("td");
      const saveMod = calc.saveMods[attr];
      tdSaveMod.textContent = `豁免 ${saveMod >= 0 ? "+" : ""}${saveMod}`;
      tdSaveMod.className = "muted";
      tr.appendChild(tdSaveMod);
```

并在 `refresh()` 末尾（`hpHint` 更新处）追加派生单元格填充：

```javascript
    document.getElementById("profBonusCell").textContent = `+${calc.profBonus}`;
    document.getElementById("initiativeCell").textContent = `${calc.initiative >= 0 ? "+" : ""}${calc.initiative}`;
    document.getElementById("hitDiceCell").textContent = calc.hitDice;
    document.getElementById("passiveCell").textContent = calc.passivePerception;
```

- [ ] **Step 5: 扩展 `readForm()`**

```javascript
  function readForm() {
    const data = { ...editing };
    const NUM_KEYS = new Set(["level", "hp", "ac", "xp", "current_hp", "temp_hp", "speed", "death_saves_success", "death_saves_fail"]);
    const LIST_KEYS = new Set(["equipment", "attacks"]);
    form.querySelectorAll("[data-f]").forEach((el) => {
      const key = el.dataset.f;
      if (key === "inspiration") return; // checkbox 单独处理
      if (NUM_KEYS.has(key)) data[key] = Number(el.value) || 0;
      else if (LIST_KEYS.has(key)) data[key] = el.value.split("\n").map((s) => s.trim()).filter(Boolean);
      else data[key] = el.value;
    });
    data.inspiration = Boolean(form.querySelector('[data-f="inspiration"]').checked);
    form.querySelectorAll("[data-attr]").forEach((el) => {
      data[el.dataset.attr] = Number(el.value) || 8;
    });
    data.proficient_skills = [...form.querySelectorAll("[data-skill]:checked")].map((el) => el.dataset.skill);
    data.saving_profs = [...form.querySelectorAll("[data-saveprof]:checked")].map((el) => el.dataset.saveprof);
    return data;
  }
```

注意：初始值填充循环对 checkbox 无效、且数组字段（equipment/attacks）需 join 成多行文本——整段替换为：

```javascript
  form.querySelectorAll("[data-f]").forEach((el) => {
    const key = el.dataset.f;
    el.value = Array.isArray(editing[key]) ? editing[key].join("\n") : (editing[key] ?? "");
  });
  const inspEl = form.querySelector('[data-f="inspiration"]');
  if (inspEl) inspEl.checked = Boolean(editing.inspiration);
```

- [ ] **Step 6: 语法与冒烟验证**

```bash
node --check checkin_gallery/static/trpg.js
python3 -m checkin_gallery & sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/profile/trpg
kill %1
```

Expected: `node --check` 无输出（语法 OK）；页面 200。浏览器手测：新建角色 → 属性行出现豁免勾选与豁免加值；战斗区显示先攻/生命骰/被动感知；资源/背景区块可填多行；保存后刷新数据保留。

- [ ] **Step 7: Commit**

```bash
git add checkin_gallery/static/trpg.js
git commit -m "feat(网页): 车卡编辑器扩展 5E 主卡面字段（豁免/战斗/资源/背景）"
```

---

### Task 4: 查看页渲染扩展（`checkin_gallery/static/char_view.js`）

**Files:**
- Modify: `checkin_gallery/static/char_view.js`

**Interfaces:**
- Consumes: Task 2 的 CharOut 新字段

- [ ] **Step 1: 扩展 `renderView`**

在 meta 行之后追加派生信息行，并在技能区之后追加 豁免/战斗/资源/背景 区（先读当前文件确认结构，按同样 `document.createElement` 风格追加）：

```javascript
  const meta2 = document.createElement("p");
  meta2.className = "muted";
  meta2.textContent = `熟练加值 +${char.prof_bonus} · 先攻 ${fmtMod(char.initiative)} · 被动感知 ${char.passive_perception} · 生命骰 ${char.hit_dice}`;
  charViewMain.appendChild(meta2);

  const saveSec = document.createElement("section");
  saveSec.className = "settings-section";
  saveSec.innerHTML = `<div class="section-head"><h2>豁免</h2></div>`;
  const saveTable = document.createElement("table");
  saveTable.className = "trpg-table";
  for (const attr of rules.attributes) {
    const mod = char.save_mods[attr];
    const prof = (char.saving_profs || []).includes(attr);
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${attr}</th><td>${prof ? "熟练" : ""}</td><td>${mod !== undefined ? fmtMod(mod) : ""}</td>`;
    saveTable.appendChild(tr);
  }
  saveSec.appendChild(saveTable);
  charViewMain.appendChild(saveSec);

  const combatSec = document.createElement("section");
  combatSec.className = "settings-section";
  combatSec.innerHTML = `<div class="section-head"><h2>战斗</h2></div>`;
  const combatTable = document.createElement("table");
  combatTable.className = "trpg-table";
  combatTable.innerHTML = `
    <tr><th>HP</th><td>${char.hp}</td><th>当前 HP</th><td>${char.current_hp || 0}</td>
        <th>临时 HP</th><td>${char.temp_hp || 0}</td></tr>
    <tr><th>AC</th><td>${char.ac}</td><th>速度</th><td>${char.speed || 30}</td>
        <th>激励</th><td>${char.inspiration ? "✓" : "—"}</td></tr>
    <tr><th>死亡豁免</th><td colspan="5">成功 ${char.death_saves_success || 0} / 失败 ${char.death_saves_fail || 0}</td></tr>`;
  combatSec.appendChild(combatTable);
  charViewMain.appendChild(combatSec);

  if ((char.equipment || []).length || char.other_proficiencies || (char.attacks || []).length || char.features) {
    const resSec = document.createElement("section");
    resSec.className = "settings-section";
    resSec.innerHTML = `<div class="section-head"><h2>资源</h2></div>`;
    const resList = document.createElement("div");
    resList.style.whiteSpace = "pre-wrap";
    const parts = [];
    if ((char.equipment || []).length) parts.push("【装备与钱币】\n" + char.equipment.join("\n"));
    if (char.other_proficiencies) parts.push("【其他熟练项和语言】\n" + char.other_proficiencies);
    if ((char.attacks || []).length) parts.push("【攻击与法术】\n" + char.attacks.join("\n"));
    if (char.features) parts.push("【特性与特质】\n" + char.features);
    resList.textContent = parts.join("\n\n");
    resSec.appendChild(resList);
    charViewMain.appendChild(resSec);
  }

  const bgFields = [
    ["个人特点", char.personality_traits], ["理想", char.ideals],
    ["牵绊", char.bonds], ["缺点", char.flaws],
  ].filter(([, v]) => v);
  if (bgFields.length) {
    const bgSec = document.createElement("section");
    bgSec.className = "settings-section";
    bgSec.innerHTML = `<div class="section-head"><h2>背景</h2></div>`;
    const bgDiv = document.createElement("div");
    bgDiv.style.whiteSpace = "pre-wrap";
    bgDiv.textContent = bgFields.map(([k, v]) => `【${k}】\n${v}`).join("\n\n");
    bgSec.appendChild(bgDiv);
    charViewMain.appendChild(bgSec);
  }
```

注意：`char_view.js` 已有 `fmtMod` 函数（查看页属性区使用），直接复用；若实际文件没有，则补一个 `function fmtMod(v) { return (v >= 0 ? "+" : "") + v; }`。

- [ ] **Step 2: 语法验证**

```bash
node --check checkin_gallery/static/char_view.js
```

Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add checkin_gallery/static/char_view.js
git commit -m "feat(网页): 角色卡查看页渲染豁免/战斗/资源/背景区块"
```

---

### Task 5: 同步维护（specs + KNOWLEDGE_BASE）

**Files:**
- Modify: `specs/web-gallery.md`
- Modify: `KNOWLEDGE_BASE.md`（或其指向的 `kb/` 细节文件）

- [ ] **Step 1: 更新 `specs/web-gallery.md` 跑团车卡章节**

补充角色卡字段清单：身份（玩家名/阵营/经验值）、属性豁免（`saving_profs`）、战斗（当前HP/临时HP/速度/死亡豁免/激励）、资源（装备 `equipment: list[str]`、其他熟练项 `other_proficiencies`、攻击 `attacks: list[str]`（`名称|加值|伤害`）、特性 `features`）、背景四要素（`personality_traits`/`ideals`/`bonds`/`flaws`）；派生计算口径（熟练加值 `2+(level-1)//4`、豁免加值、被动感知 `10+感知加值+(察觉熟练?2:0)`、先攻=敏捷加值、生命骰 `{level}d{职业骰}`）不入盘、由 `finalize` 计算。

- [ ] **Step 2: 更新 `KNOWLEDGE_BASE.md` / `kb/QUICK_REFERENCE.md`**

角色卡 JSON 结构补充新字段与派生字段说明（与 web-gallery 同口径，简短记录键名清单与派生公式）。

- [ ] **Step 3: 全量回归**

```bash
python3 test/test_trpg_finalize.py
python3 test/test_character_store.py
python3 test/test_user_settings.py
python3 test/test_trpg.py
python3 test/test_trpg_char.py
python3 test/test_trpg_session.py
python3 test/test_dice.py
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add specs/web-gallery.md KNOWLEDGE_BASE.md kb/
git commit -m "docs(跑团): 同步 5E 主卡面字段与派生计算口径至 specs 与知识库"
```
