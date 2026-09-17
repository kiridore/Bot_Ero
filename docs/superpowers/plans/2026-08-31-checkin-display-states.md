# 打卡时间线显示状态四态化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 个人隐私设置升级为**按打卡类型**（私聊/网页打卡 vs 群聊打卡）的**四态显示状态**：显示 / 模糊显示 / 仅显示打卡信息（不含图片）/ 完全隐藏，替换现有两个布尔开关。

**Architecture:** 设置沿用 `core/user_settings.py` JSON，新键 `privacy.checkin_display_private` / `privacy.checkin_display_group`（字符串枚举 `show|blur|text|hidden`，缺省 `show`），旧布尔键**一次性懒迁移后删除**；读侧（webapp/timeline/app.py）将现有 hidden/blur 二维上下文扩展为按事件类型取态——hidden 沿用现机制（含作者自见 + 「仅自己可见」角标），blur 沿用 URL 改写，**text 为新态**：非作者查看时剥离图片并附 `images_hidden: true` 标记，前端渲染右下角角注「图片仅作者可见」；作者本人任何状态均看原图。设置页两个 checkbox 换成两组 radio（每类打卡 4 选 1）。

**Tech Stack:** 同前（纯同步 bot / FastAPI / pytest + node DOM stub）。

**Spec:** specs/web-gallery.md 时间线可见性节（本计划落地时更新）；core/user_settings.py 键约定文档。

## 需求裁定记录（用户已确认）

1. 完全隐藏保留（私聊打卡现状能力不回退）。
2. 旧键 `privacy.private_checkin_public` / `privacy.checkin_image_public` **废除**，一次性迁移：`private_checkin_public=false` → 私聊=`hidden`；`checkin_image_public=false` → 两类均=`blur`；其余 → `show`。两旧规则同时命中时私聊取 `hidden`（更强态优先）。
3. 作者本人任何状态下看自己打卡始终原图；「仅文字」卡片对他人加角注。
4. 设置页用 radio 替换 checkbox：两行（私聊/网页打卡、群聊打卡）各四选一。

## 计划内假设（可 veto）

- **A1** 群聊打卡同样为四态（含完全隐藏）——「保留」的对称解读；若群聊只做三态（无隐藏），砍掉对应 radio 与 hidden 分支即可。
- **A2** 迁移在首次读取设置时懒执行并**回写删除旧键**（用户 JSON 中不再残留）；之后旧键被完全忽略。
- **A3** 「仅文字」角注文案：**「图片仅作者可见」**，右下角，复用 `.tl-blur-note` 同款样式（新增 `.tl-text-note` 或共用类）；模糊角注「作者已开启图片模糊」不变。
- **A4** poll/new 计数口径：仅 `hidden` 参与过滤（现状）；`blur`/`text` 事件可见，计数不变。
- **A5** 无旧键且无新键的用户（从未设置过）→ 两类均 `show`。

## Global Constraints

- bot 禁 async；webapp 新代码同步 def；SQL 全 `?` 参数化。
- Commit 中文 Conventional；文档同 commit；整分支一个 minor → 最终统一 bump **1.28.0** + CHANGELOG。
- 测试不触真实 data.db/server_data；"/tmp" = F:/tmp。
- 状态枚举值 `show|blur|text|hidden` 为代码契约，三处（user_settings / timeline 读侧 / settings.js）必须一致。

---

### Task 1: 设置模型四态化 + 旧键一次性迁移（core/user_settings.py）

**Files:**
- Modify: `core/user_settings.py`
- Test: 新建 `test/test_checkin_display_settings.py`

**Interfaces:**
- Produces: `CHECKIN_DISPLAY_STATES = ("show", "blur", "text", "hidden")`；`checkin_display(user_id) -> dict` 返回 `{"private": <state>, "group": <state>}`，读取时懒迁移旧键并回写；旧函数 `private_checkin_public` / `checkin_image_public` **删除**（唯一调用方 Task 3 改掉）。
- 下游消费：Task 3（timeline 读侧）、Task 2（settings.js 不经 helper，直接读写新键）。

- [ ] **Step 1: 失败测试** — `test/test_checkin_display_settings.py`：

```python
"""打卡显示状态四态设置与旧键一次性迁移回归。运行: pytest test/test_checkin_display_settings.py"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import user_settings as us


class TestCheckinDisplay(unittest.TestCase):
    def setUp(self):
        import shutil
        us.SETTINGS_ROOT = Path("/tmp/test_checkin_display")
        shutil.rmtree(us.SETTINGS_ROOT, ignore_errors=True)

    def _write(self, uid, privacy):
        us.update_settings(uid, {"privacy": privacy})

    def test_default_show(self):
        self.assertEqual(us.checkin_display("1"), {"private": "show", "group": "show"})

    def test_roundtrip_all_states(self):
        for state in us.CHECKIN_DISPLAY_STATES:
            self._write("2", {"checkin_display_private": state, "checkin_display_group": state})
            self.assertEqual(us.checkin_display("2"), {"private": state, "group": state})

    def test_migration_old_private_false(self):
        self._write("3", {"private_checkin_public": False})
        d = us.checkin_display("3")
        self.assertEqual(d, {"private": "hidden", "group": "show"})
        raw = us.get_settings("3").get("privacy", {})  # 迁移已回写，旧键删除
        self.assertNotIn("private_checkin_public", raw)
        self.assertNotIn("checkin_image_public", raw)

    def test_migration_old_image_false(self):
        self._write("4", {"checkin_image_public": False})
        self.assertEqual(us.checkin_display("4"), {"private": "blur", "group": "blur"})

    def test_migration_both_old_keys_hidden_wins_for_private(self):
        self._write("5", {"private_checkin_public": False, "checkin_image_public": False})
        self.assertEqual(us.checkin_display("5"), {"private": "hidden", "group": "blur"})

    def test_migration_ignored_when_new_keys_exist(self):
        self._write("6", {"checkin_display_private": "text", "private_checkin_public": False})
        self.assertEqual(us.checkin_display("6"), {"private": "text", "group": "show"})

    def test_invalid_value_falls_back_show(self):
        self._write("7", {"checkin_display_private": "爆炸"})
        self.assertEqual(us.checkin_display("7")["private"], "show")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: RED** — `python -m pytest test/test_checkin_display_settings.py -v` → AttributeError: no checkin_display。
- [ ] **Step 3: 实现**（替换旧两个 helper 及其键约定注释行）：

```python
CHECKIN_DISPLAY_STATES = ("show", "blur", "text", "hidden")


def checkin_display(user_id) -> dict:
    """打卡时间线显示状态（按类型）：{"private": state, "group": state}。

    state ∈ show|blur|text|hidden；缺省 show。首次读取时懒迁移旧布尔键
    （private_checkin_public / checkin_image_public）并回写删除——旧键已废除。
    """
    uid = str(user_id)
    with _lock_for(uid):
        settings = _read(_settings_path(uid))
        privacy = settings.get("privacy", {})
        changed = False
        if "checkin_display_private" not in privacy or "checkin_display_group" not in privacy:
            if "checkin_display_private" not in privacy:
                privacy["checkin_display_private"] = (
                    "hidden" if privacy.get("private_checkin_public") is False
                    else ("blur" if privacy.get("checkin_image_public") is False else "show")
                )
                changed = True
            if "checkin_display_group" not in privacy:
                privacy["checkin_display_group"] = (
                    "blur" if privacy.get("checkin_image_public") is False else "show"
                )
                changed = True
        for legacy in ("private_checkin_public", "checkin_image_public"):
            if legacy in privacy:
                privacy.pop(legacy)
                changed = True
        if changed:
            settings["privacy"] = privacy
            _write(_settings_path(uid), settings)
    def _valid(v):
        return v if v in CHECKIN_DISPLAY_STATES else "show"
    return {"private": _valid(privacy.get("checkin_display_private", "show")),
            "group": _valid(privacy.get("checkin_display_group", "show"))}
```

（照 `update_settings` 的锁与原子写模式；`privacy` 局部变量在锁内赋值。）

- [ ] **Step 4: GREEN + 全量回归** — 旧函数删除后 `webapp/timeline/app.py` 的 import 会挂，放同一 commit 内改为等价新语义：`_visibility_ctx` 改用 `checkin_display()`，`private_public=False ⇔ state=="hidden"`、`image_public=False ⇔ 任一类型 state=="blur"` 的行为映射零变化（text 态 Task 3 展开）。跑 `python -m pytest -q` 全绿。
- [ ] **Step 5: Commit** — `refactor(设置): 打卡显示状态四态化并一次性迁移废除旧布尔键`

---

### Task 2: 设置页 radio 化（webapp/static/settings.js）

**Files:**
- Modify: `webapp/static/settings.js`
- Test: 修改 `test/test_settings_render.js`

**Interfaces:**
- Consumes: 新键 `privacy.checkin_display_private` / `checkin_display_group`（值 `show|blur|text|hidden`）。
- Produces: 两组 radio（每类打卡 4 选 1），选中态 = API 返回值（缺失按 show）；变更即 PUT 单键。

- [ ] **Step 1: 失败测试** — `test/test_settings_render.js`：空 privacy → 两组各 4 个 radio 且 `show` 选中；返回 `{"checkin_display_private": "text"}` → 私聊组 `text` 选中；点击群聊组 `hidden` radio → PUT body 含 `{"privacy": {"checkin_display_group": "hidden"}}`；**旧 checkbox 断言删除**。
- [ ] **Step 2: RED** → **Step 3: 实现**：替换两个 checkbox 渲染为两组 radio（沿用现有行结构/类名；name=`checkinDisplayPrivate` / `checkinDisplayGroup`；value=四态；label 文案：显示 / 模糊显示 / 仅打卡信息 / 隐藏；行标题「私聊/网页打卡在时间线上」「群聊打卡在时间线上」）；change 事件 PUT 单键 `{privacy: {checkin_display_xxx: value}}`。
- [ ] **Step 4: GREEN** + `node test/test_settings_render.js` + dom 套件。
- [ ] **Step 5: Commit** — `feat(设置): 打卡时间线显示状态改为按类型四选一单选`

---

### Task 3: 读侧按类型四态（webapp/timeline/app.py + 隐私脚本）

**Files:**
- Modify: `webapp/timeline/app.py`
- Test: 修改 `test/scripts/check_timeline_privacy.py`

**Interfaces:**
- Consumes: Task 1 `checkin_display`；事件 `data.private`（类型判定）。
- Produces: 序列化事件新增 `"images_hidden": true`（非作者查看 text 态打卡时）；blur/hidden 语义不变但按类型判定。

- [ ] **Step 1: 失败测试** — 扩展 `check_timeline_privacy.py`：作者 A 种私聊+群聊事件，B 种事件；设置 A：`checkin_display_private="text"`、`checkin_display_group="blur"`。断言：
  1. 查看者 C：A 私聊事件无 `data.images`（或空）且 `images_hidden == true`；A 群聊图 URL 带 blur=1 且无 images_hidden。
  2. A 自看：两类均原图、无 blur=1、无 images_hidden；hidden 态事件仍 self_only。
  3. A 改 `checkin_display_group="hidden"` → C 的 feed/poll/new 看不到 A 群聊事件（复用现过滤断言）；A 自见 + self_only。
  4. 全 hidden 的既有空页/500 回归用例保持绿。
- [ ] **Step 2: RED** → **Step 3: 实现**：
  - `_visibility_ctx`：`actor_flags[key] = checkin_display(key)`（dict）；每事件 `state = flags["private" if data.private else "group"]` → `hidden` 入 hidden 集；`blur` 入 blur 集；`text` 入新 `text_ids` 集（事件粒度，非作者集）。
  - `_serialize_rows`：非作者 + eid ∈ text_ids → `data` 剥离 `images`（置空列表）+ 事件 dict 加 `"images_hidden": True`；blur 逻辑不变（按事件类型入集，不再按作者全量模糊）。
  - poll 过滤口径不变（仅 hidden）。
- [ ] **Step 4: GREEN** + `python test/scripts/check_timeline_privacy.py` + webapp 套件。
- [ ] **Step 5: 同 commit 更新 `specs/web-gallery.md`**（四态规则、images_hidden 字段、迁移语义、poll/new 口径）。
- [ ] **Step 6: Commit** — `feat(时间线): 打卡事件按类型四态显示隐藏模糊与仅文字`

---

### Task 4: 前端「图片仅作者可见」角注（timeline.js/css）

**Files:**
- Modify: `webapp/static/timeline.js`、`webapp/static/timeline.css`
- Test: 修改 `test/test_timeline_render.js`

- [ ] **Step 1: 失败测试** — 夹具事件带 `images_hidden: true`（无 images），断言卡片含角注元素 class `tl-text-note` 文本「图片仅作者可见」；普通卡与模糊卡无此角注（模糊卡仍只有 tl-blur-note）。
- [ ] **Step 2: RED** → **Step 3: 实现** — renderEvent 内（图片条同级/之后）：

```javascript
    if (ev.images_hidden) {
      const note = document.createElement("span");
      note.className = "tl-text-note";
      note.textContent = "图片仅作者可见";
      item.appendChild(note);
    }
```

  CSS `.tl-text-note` 与 `.tl-blur-note` 同款（右下角绝对定位；两注互斥不会同卡共存）。
- [ ] **Step 4: GREEN** + dom 套件 → **Step 5: Commit** — `feat(时间线): 仅文字打卡卡片右下角显示图片仅作者可见角注`

---

### Task 5: 版本收尾 1.28.0

- [ ] core/config.py bump `1.27.0 → 1.28.0`；CHANGELOG `[1.28.0]` 新增（四态设置 + 迁移 + images_hidden 角注，文案覆盖"旧开关废除自动迁移"用户可见行为）。
- [ ] 全量 `python -m pytest` + `node test/test_timeline_render.js` 全绿。
- [ ] Commit — `chore(版本): 1.28.0 打卡时间线显示状态四态化`

## 收尾核验

- 5 commit；`BOTERO_VERSION == "1.28.0"`；specs/web-gallery.md 四态规则与实现一致；grep 全库无 `private_checkin_public|checkin_image_public` 残留引用（core/user_settings.py 迁移代码内的字面量除外）。
- 场景：C 看 A 私聊 text=无图+角注、群聊 blur=模糊图、群聊 hidden=不可见；A 自看全原图；poll 计数仅 hidden 口径。

## 明确不做

- 不加"作者自看模糊/仅文字预览"；不动 bot 侧；不回填历史；poll/new 不为 text/blur 改口径；图库页不受影响（沿 A4 旧裁定）。
