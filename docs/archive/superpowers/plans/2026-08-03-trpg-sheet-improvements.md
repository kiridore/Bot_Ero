# 5E 车卡改进（玩家名/阵营/属性生成/下拉/经验等级）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 改进 5E 网页车卡：删除玩家名字段（绑定 QQ）、阵营改九宫格双下拉、属性生成支持 购点/4d6k3 掷骰/标准数组 三种方式、种族/职业改纯官方清单 select、等级由经验值派生。

**Architecture:** 规则数据（XP 阈值表）进 `core/trpg/rules.py` 单一数据源；`level_from_xp()` 与 `finalize()` 的 level 派生在 `core/trpg/character.py`（xp>0 时派生，否则回退已存 level）；API 层删除 `player_name`、`level` 改可选并承担旧数据 xp 迁移；前端 `trpg.js` 改造表单控件。骰子契约不变。

**Tech Stack:** Python stdlib、FastAPI（`checkin_gallery/app.py`）、vanilla JS（`checkin_gallery/static/trpg.js` / `char_view.js`）。

## Global Constraints

- **xp 主导**：`xp` 是等级唯一来源；`level` 派生不入盘（旧数据读侧回退已存 level）；保存时若 xp 缺失/0 且 level>1，自动迁移 `xp = XP_THRESHOLDS[level-1]`（官方：高等级开始 = 该级最小 XP）。
- **XP 阈值表**（rules.py，与 CHM 玩家手册核对）：`[0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]`（索引 0=1 级）。
- **阵营九种**：秩序（守序/中立/混乱）× 道德（善良/中立/邪恶）；中立×中立 = 「绝对中立」。存储 `alignment` 为组合字符串。
- **种族/职业纯官方清单**：select 选项 = `rules.races`/`rules.classes` 键（8 种族 12 职业），不允许自定义文本；旧角色含自定义文本时读侧兼容（select 临时加入该值选项）。
- **玩家名删除**：`player_name` 从 UI/CharacterIn/CharOut 移除（旧 JSON 中的键无害，不清理）。
- 标准键契约不变；旧角色兼容；无 async/无 SQL/无框架；中文 Conventional Commits；`python3 test/<name>.py`。
- 同步维护（同 commit）：`specs/web-gallery.md`、`KNOWLEDGE_BASE.md`/`kb/QUICK_REFERENCE.md`。

---

### Task 1: XP 阈值表 + level 派生（rules.py / character.py）

**Files:**
- Modify: `core/trpg/rules.py`（新增 `XP_THRESHOLDS`）
- Modify: `core/trpg/character.py`（新增 `level_from_xp()`，`finalize()` 用 xp 派生 level）
- Create: `test/test_trpg_finalize.py`（追加用例）

**Interfaces:**
- Consumes: 无
- Produces: `rules.XP_THRESHOLDS: list[int]`（20 项）；`character.level_from_xp(xp: int) -> int`；`finalize()` 的 `level` 键 = xp>0 ? 派生 : 已存 level（`out["level"]` 覆盖为派生值）

- [ ] **Step 1: 追加失败测试到 `test/test_trpg_finalize.py`**

```python
from core.trpg.rules import XP_THRESHOLDS


class TestLevelFromXp(unittest.TestCase):
    def test_thresholds_table(self):
        self.assertEqual(len(XP_THRESHOLDS), 20)
        self.assertEqual(XP_THRESHOLDS[0], 0)
        self.assertEqual(XP_THRESHOLDS[19], 355000)

    def test_level_boundaries(self):
        from core.trpg.character import level_from_xp
        self.assertEqual(level_from_xp(0), 1)
        self.assertEqual(level_from_xp(299), 1)
        self.assertEqual(level_from_xp(300), 2)
        self.assertEqual(level_from_xp(6500), 5)
        self.assertEqual(level_from_xp(100000), 12)
        self.assertEqual(level_from_xp(355000), 20)
        self.assertEqual(level_from_xp(999999), 20)

    def test_finalize_level_derived_from_xp(self):
        data = finalize(_base(xp=6500, level=1))
        self.assertEqual(data["level"], 5)
        self.assertEqual(data["prof_bonus"], 3)

    def test_finalize_level_fallback_to_stored(self):
        data = finalize(_base(xp=0, level=7))
        self.assertEqual(data["level"], 7)

    def test_finalize_xp_zero_level_one(self):
        data = finalize(_base(xp=0, level=1))
        self.assertEqual(data["level"], 1)
```

（`_base` 已在文件顶部定义；若 `xp` 键不在 `_base` 中，通过 `_base(xp=...)` 传入——确认 `_base` 支持 kwargs 合并，若不支持则在测试内 `data.update({"xp": ...})`。）

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 test/test_trpg_finalize.py`
Expected: FAIL（`XP_THRESHOLDS` 不存在 / `level_from_xp` 不存在）

- [ ] **Step 3: 实现 `rules.py` 与 `character.py`**

`core/trpg/rules.py` 末尾追加：

```python
# 升级经验阈值：索引 0 = 1 级，共 20 级
XP_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
]
```

`core/trpg/character.py` 新增函数（放在 `finalize` 之前）：

```python
def level_from_xp(xp: int) -> int:
    """由经验值反推等级（1-20）。"""
    level = 1
    for i, threshold in enumerate(XP_THRESHOLDS, start=1):
        if xp >= threshold:
            level = i
    return level
```

（import 增加 `XP_THRESHOLDS`。）`finalize` 内修改（在 `level = int(char_data.get("level", 1))` 之前插入）：

```python
    xp = int(char_data.get("xp", 0))
    level = level_from_xp(xp) if xp > 0 else int(char_data.get("level", 1))
    out["level"] = level
```

将原 `level = int(char_data.get("level", 1))` 行删除（prof_bonus/hit_dice 均用新 `level`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 test/test_trpg_finalize.py` + 回归 `python3 test/test_trpg.py`、`python3 test/test_trpg_char.py`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/trpg/rules.py core/trpg/character.py test/test_trpg_finalize.py
git commit -m "feat(跑团): 新增 XP 阈值表与等级派生计算"
```

---

### Task 2: API 层（`checkin_gallery/app.py`）

**Files:**
- Modify: `checkin_gallery/app.py`

**Interfaces:**
- Consumes: `rules.XP_THRESHOLDS`（Task 1）
- Produces: `CharacterIn` 无 `player_name`、`level: int = 1`（可选）；`CharOut` 无 `player_name`；POST/PUT 保存时旧数据 xp 迁移；`/api/trpg/rules` 新增 `xp_thresholds` 与 `alignments`（九种）

- [ ] **Step 1: 修改 `CharacterIn`**

删除 `player_name: str = ""` 行；`level: int = 1` 保持不变（可选默认 1，前端不再提交 level，由 xp 派生）。

- [ ] **Step 2: 修改 `CharOut` 与 `_char_to_out`**

删除 `player_name: str` 字段及 `_char_to_out` 中对应行。

- [ ] **Step 3: 保存时 xp 迁移（`api_create_character` 与 `api_update_character` 中 finalize 之前）**

两个端点都在 `data = body.model_dump()` 后加：

```python
    if int(data.get("xp", 0)) <= 0 and int(data.get("level", 1)) > 1:
        data["xp"] = trpg_rules.XP_THRESHOLDS[int(data["level"]) - 1]
```

- [ ] **Step 4: `/api/trpg/rules` 返回新数据**

```python
        "xp_thresholds": trpg_rules.XP_THRESHOLDS,
        "alignments": {
            "law": ["守序", "中立", "混乱"],
            "moral": ["善良", "中立", "邪恶"],
        },
```

（九种组合由前端两轴交叉生成；「绝对中立」命名由前端处理。）

- [ ] **Step 5: 冒烟验证**

```bash
python3 -m checkin_gallery & sleep 2
KEY=$(python3 -c "from checkin_gallery.auth import make_login_key; print(make_login_key('123456'))")
# 旧角色迁移：POST level=5 无 xp → 响应 xp=6500, level=5
curl -s -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8765/api/me/characters \
  -d '{"char_name":"测试","race":"人类","class_name":"战士","level":5,"str_score":15,"dex_score":14,"con_score":13,"int_score":12,"wis_score":10,"cha_score":8}' | python3 -m json.tool | grep -E '"xp"|"level"'
curl -s http://127.0.0.1:8765/api/trpg/rules | grep -o '"xp_thresholds".\{0,40\}'
kill %1; rm -rf server_data/trpg_chars/123456
```

Expected: 响应 `xp: 6500` 且 `level: 5`；rules 含 `xp_thresholds`

- [ ] **Step 6: Commit**

```bash
git add checkin_gallery/app.py
git commit -m "feat(网页): API 移除玩家名、新增经验等级派生与迁移、规则接口返回阵营/经验表"
```

---

### Task 3: 编辑器改造（`checkin_gallery/static/trpg.js`）

**Files:**
- Modify: `checkin_gallery/static/trpg.js`

**Interfaces:**
- Consumes: `/api/trpg/rules` 的 `alignments`/`xp_thresholds`（Task 2）
- Produces: 无

**改动点：**

- [ ] **Step 1: 种子对象**：删除 `player_name: ""`；`alignment: "绝对中立"`（默认值）；`xp: 0` 保留。

- [ ] **Step 2: 基本信息区 HTML 改造**（替换原 玩家名/阵营/经验值 两行）

```html
        <tr><th>阵营</th><td>
            <select data-f="alignment_law">
              <option value="守序">守序</option><option value="中立">中立</option><option value="混乱">混乱</option>
            </select>
            <select data-f="alignment_moral">
              <option value="善良">善良</option><option value="中立">中立</option><option value="邪恶">邪恶</option>
            </select>
            <input type="text" data-f="alignment_custom" placeholder="自定义阵营（非九宫格）" style="display:none;">
          </td>
            <th>经验值</th><td><input type="number" data-f="xp" min="0"></td></tr>
        <tr><th>等级</th><td id="levelCell"></td>
            <th>熟练加值</th><td id="profBonusCell"></td></tr>
```

（`alignment_law`/`alignment_moral`/`alignment_custom` 为虚拟键——不被 readForm 直接收集，见 Step 5。`levelCell` 显示派生等级。）

- [ ] **Step 3: 种族/职业 input → select**

```html
        <tr><th>角色名</th><td><input type="text" data-f="char_name" maxlength="30"></td>
            <th>种族</th><td><select data-f="race"></select></td></tr>
        <tr><th>职业</th><td><select data-f="class_name"></select></td>
            <th>等级</th>...（见 Step 2，等级行已在阵营行内）
```

移除原 `datalist` 填充循环，改为 select 填充（在 `raceList`/`classList` 代码处替换）：

```javascript
  const raceSelect = form.querySelector('[data-f="race"]');
  for (const r of Object.keys(rules.races)) {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    raceSelect.appendChild(opt);
  }
  const classSelect = form.querySelector('[data-f="class_name"]');
  for (const c of Object.keys(rules.classes)) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    classSelect.appendChild(opt);
  }
  // 旧角色自定义文本兼容：不在官方清单时追加临时选项
  for (const [sel, key] of [[raceSelect, "race"], [classSelect, "class_name"]]) {
    if (editing[key] && ![...sel.options].some((o) => o.value === editing[key])) {
      const opt = document.createElement("option");
      opt.value = editing[key];
      opt.textContent = `${editing[key]}（自定义）`;
      sel.appendChild(opt);
    }
  }
```

删除 HTML 中 `<datalist id="raceList"></datalist><datalist id="classList"></datalist>`。

- [ ] **Step 4: 属性生成方式区**（属性区标题行后插入）

```html
    <section class="settings-section">
      <div class="section-head"><h2>属性生成</h2></div>
      <div class="row-actions">
        <button type="button" class="btn-sm" id="genPointBuy">购点法（27点）</button>
        <button type="button" class="btn-sm" id="genRoll">4d6k3 掷骰</button>
        <button type="button" class="btn-sm" id="genArray">标准数组</button>
        <span class="muted" id="pointBuyHint"></span>
      </div>
    </section>
```

（插在现有属性区 `<section>` 之前；`genPointBuy` 点击后展开购点子面板——简化：点击购点按钮切换购点模式，属性输入框 min=8 max=15，`pointBuyHint` 实时显示 `剩余 N 点`；掷骰/标准数组点击后直接填值。）

事件逻辑（放在 `refresh` 定义后）：

```javascript
  function rollScores() {
    const scores = [];
    for (let i = 0; i < 6; i++) {
      const rolls = [];
      for (let j = 0; j < 4; j++) rolls.push(1 + Math.floor(Math.random() * 6));
      rolls.sort((a, b) => b - a);
      scores.push(rolls[0] + rolls[1] + rolls[2]);
    }
    return scores;
  }
  const arrayScores = [15, 14, 13, 12, 10, 8];

  form.querySelector("#genRoll").addEventListener("click", () => {
    const vals = rollScores();
    form.querySelectorAll("[data-attr]").forEach((el, i) => { el.value = vals[i]; });
    refresh();
  });
  form.querySelector("#genArray").addEventListener("click", () => {
    form.querySelectorAll("[data-attr]").forEach((el, i) => { el.value = arrayScores[i]; });
    refresh();
  });
  form.querySelector("#genPointBuy").addEventListener("click", () => {
    form.querySelectorAll("[data-attr]").forEach((el) => { el.min = 8; el.max = 15; });
    showToast("购点模式：属性值 8-15，总花费不超过 27 点");
    refresh();
  });
```

购点剩余点数实时提示（`refresh` 末尾追加）：

```javascript
    const pointCost = {8:0,9:1,10:2,11:3,12:4,13:5,14:7,15:9};
    let spent = 0;
    form.querySelectorAll("[data-attr]").forEach((el) => {
      const v = Number(el.value) || 8;
      if (pointCost[v] !== undefined) spent += pointCost[v];
    });
    const hint = document.getElementById("pointBuyHint");
    hint.textContent = `购点已用 ${spent}/27`;
```

- [ ] **Step 5: `readForm` 扩展（阵营组合 + level 移除）**

```javascript
    // 阵营：双下拉组合，或自定义文本
    const law = form.querySelector('[data-f="alignment_law"]').value;
    const moral = form.querySelector('[data-f="alignment_moral"]').value;
    const custom = form.querySelector('[data-f="alignment_custom"]').value.trim();
    if (custom) data.alignment = custom;
    else data.alignment = law === "中立" && moral === "中立" ? "绝对中立" : law + moral;
    // level 不手动编辑，但保留旧值提交——供后端做旧角色 xp 迁移（level>1 且 xp=0 → xp=阈值下限）
    data.level = editing.level ?? 1;
```

（`NUM_KEYS` 中删除 `level`；`data.xp` 正常收集。注意：**不要** `delete data.level`——否则旧角色保存时 level 回落到后端默认 1，迁移条件不触发，旧角色会降级为 1 级。）

- [ ] **Step 6: 初始填充与派生显示**

填充循环后追加阵营拆分与等级显示：

```javascript
  const lawSel = form.querySelector('[data-f="alignment_law"]');
  const moralSel = form.querySelector('[data-f="alignment_moral"]');
  const customSel = form.querySelector('[data-f="alignment_custom"]');
  const AL = ["守序善良", "守序中立", "守序邪恶", "中立善良", "绝对中立", "中立邪恶", "混乱善良", "混乱中立", "混乱邪恶"];
  if (AL.includes(editing.alignment)) {
    if (editing.alignment === "绝对中立") { lawSel.value = "中立"; moralSel.value = "中立"; }
    else {
      lawSel.value = editing.alignment.startsWith("守序") ? "守序" : editing.alignment.startsWith("混乱") ? "混乱" : "中立";
      moralSel.value = editing.alignment.endsWith("善良") ? "善良" : editing.alignment.endsWith("邪恶") ? "邪恶" : "中立";
    }
    customSel.style.display = "none";
  } else if (editing.alignment) {
    customSel.style.display = "";
    customSel.value = editing.alignment;
  }
```

`refresh` 末尾追加等级显示：

```javascript
    const xpVal = Number(data.xp) || 0;
    const level = xpVal > 0 ? levelFromXp(xpVal, rules.xp_thresholds) : (data.level || 1);
    document.getElementById("levelCell").textContent = `Lv.${level}`;
```

新增顶层函数：

```javascript
function levelFromXp(xp, thresholds) {
  let level = 1;
  thresholds.forEach((t, i) => { if (xp >= t) level = i + 1; });
  return level;
}
```

- [ ] **Step 7: 语法与冒烟验证**

```bash
node --check checkin_gallery/static/trpg.js
```

Expected: 无输出。浏览器手测：阵营双下拉组合正确（含绝对中立）；种族/职业下拉显示全部官方选项；掷骰/标准数组按钮填值；购点提示剩余点数；等级随 xp 输入实时变化；编辑旧自定义种族角色显示"（自定义）"选项。

- [ ] **Step 8: Commit**

```bash
git add checkin_gallery/static/trpg.js
git commit -m "feat(网页): 车卡编辑器改进——阵营九宫格/官方清单下拉/属性生成三方式/经验派生等级"
```

---

### Task 4: 查看页清理（`checkin_gallery/static/char_view.js`）

**Files:**
- Modify: `checkin_gallery/static/char_view.js`

- [ ] **Step 1: 删除玩家名显示**

`renderView` 中 meta 行若显示 `player_name`（检查：现查看页 meta 行显示 `char.display_name` 的角色卡，不含 player_name——若实际无则跳过）。全局搜索 `player_name`，删除相关渲染行。

- [ ] **Step 2: 语法验证**

```bash
node --check checkin_gallery/static/char_view.js
```

- [ ] **Step 3: Commit**

```bash
git add checkin_gallery/static/char_view.js
git commit -m "refactor(网页): 查看页移除玩家名显示"
```

---

### Task 5: 同步维护

**Files:**
- Modify: `specs/web-gallery.md`
- Modify: `KNOWLEDGE_BASE.md` / `kb/QUICK_REFERENCE.md`

- [ ] **Step 1: 更新文档**

- `specs/web-gallery.md` 跑团车卡章节：`player_name` 字段移除；`alignment` 说明改为九宫格（守序/中立/混乱 × 善良/中立/邪恶，中立×中立=绝对中立，存储组合字符串）；`level` 改为派生（xp 阈值表，`xp_thresholds` 键）；属性生成三方式；种族/职业为官方清单 select（自定义文本仅旧数据读侧兼容）。
- `kb/QUICK_REFERENCE.md`：角色卡键表更新（删 player_name、level 派生说明、xp_thresholds 规则键）。

- [ ] **Step 2: 全量回归**

```bash
python3 test/test_trpg_finalize.py test/test_character_store.py test/test_user_settings.py test/test_trpg.py test/test_trpg_char.py test/test_trpg_session.py test/test_dice.py
```

Expected: 全部 PASS（逐一运行）

- [ ] **Step 3: Commit**

```bash
git add specs/web-gallery.md KNOWLEDGE_BASE.md kb/
git commit -m "docs(跑团): 同步阵营九宫格/属性生成/经验等级派生至 specs 与知识库"
```
