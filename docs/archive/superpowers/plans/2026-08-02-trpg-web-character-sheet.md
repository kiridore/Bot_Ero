# 跑团网页端在线车卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为跑团包新增基于现有 `checkin_gallery` 网页架构的在线车卡（Excel 式单页分区表格填写 + 查看），角色卡数据从 SQLite 迁移到纯 JSON 文件存储，并沉淀通用个人设置体系（隐私开关为首个用例）。

**Architecture:** 纯 JSON 文件存储（每角色一文件 + 每用户 meta.json，`server_data/trpg_chars/`），纯 stdlib 模块 `core/character_store.py` 与 `core/user_settings.py` 供 bot 与 web 双进程共用；规则计算逻辑从 `plugins/trpg_char/` 迁移到 `core/trpg/`（`core/__init__.py` 为空，import 无副作用）；FastAPI 新增车卡/设置/规则端点 + 两个新页面（管理页、查看页）；QQ 端 `/角色` 精简为 查看(仅自己)/列表/切换/删除。

**Tech Stack:** Python stdlib（全部文件 I/O）、FastAPI、vanilla JS 静态页（沿用 `checkin_gallery/static/` 现有 profile 系列模式）。

## Global Constraints

- **无 async/await**：系统是同步 threading 架构；FastAPI 现有端点也全是同步 def（沿用）。
- **新增代码中不得出现 SQL**（本次删除 SQL 表）。
- **规则数据单一来源**：`core/trpg/rules.py` 是唯一规则数据源；前端通过 `GET /api/trpg/rules` 获取，不得内嵌静态副本。
- **标准键契约不变**：角色 JSON 中 6 属性键 `str_score`/`dex_score`/`con_score`/`int_score`/`wis_score`/`cha_score`、技能名（中文）、`proficient_skills`、`char_name`/`race`/`class_name`/`level`/`hp`/`ac`/`notes` 必须保留——`trpg_dice` 依赖。
- **路径安全性**：`user_id` 只允许数字字符串（`.isdigit()`），`char_id` 只允许正整数；禁止从输入拼接路径。
- **原子写**：所有 JSON 写入先写 `*.tmp` 再 `os.replace()`。
- **提交规范**：中文 Conventional Commits；相关 `specs/`、`plugins/menu/bot_menu_text.py`、`KNOWLEDGE_BASE.md` 必须与代码同 commit。
- **测试**：无框架，`test/` 目录 ad-hoc unittest 脚本，`python test/<name>.py` 运行。
- **数据放弃**：旧 `dnd_characters` / `dnd_current_character` 表数据为开发期测试数据，直接删除表结构，不做迁移。
- 项目已有 `character_store` 语义：`core/db/character.py` 中 `CharacterManager` 将被整体删除并替换为 `core/character_store.py`。
- **网页地址**：QQ 端提示语中的网页地址用 `http://127.0.0.1:8765` 与 `checkin_gallery/config.py` 的 `HOST`/`PORT` 一致（若部署环境不同由使用者按 env 配置）。

---

### Task 1: 迁移规则模块到 `core/trpg/`

**Files:**
- Create: `core/trpg/__init__.py`（空文件）
- Create: `core/trpg/rules.py`（内容 = 现有 `plugins/trpg_char/rules.py` 原样复制）
- Create: `core/trpg/character.py`（内容 = 现有 `plugins/trpg_char/character.py` 原样复制，`from .rules import ...` 不变）
- Modify: `plugins/trpg_char/rules.py` → 改为 re-export
- Modify: `plugins/trpg_char/character.py` → 改为 re-export
- Test: `test/test_trpg.py`（现有，回归）

**Interfaces:**
- Produces: `core/trpg/rules.py` 导出 `ATTRIBUTES`、`ATTRIBUTE_EN`、`SKILLS`、`SKILL_ALIASES`、`RACES`、`CLASSES`、`POINT_BUY_COST`、`POINT_BUY_BUDGET`、`STANDARD_ARRAY`、`ability_modifier(score) -> int`、`skill_attribute(skill) -> str`、`race_bonuses(race) -> dict`、`class_info(class_name) -> dict`；`core/trpg/character.py` 导出 `finalize(char_data: dict) -> dict`、`get_attr_value(char_data, name) -> int | None`、`resolve_expression_values(char_data) -> dict`、`format_sheet(char_data) -> str`

- [ ] **Step 1: 复制并清空 `core/trpg/__init__.py`**

```bash
mkdir -p core/trpg
cp plugins/trpg_char/rules.py core/trpg/rules.py
cp plugins/trpg_char/character.py core/trpg/character.py
touch core/trpg/__init__.py
```

- [ ] **Step 2: 将 `plugins/trpg_char/rules.py` 改为 re-export**

```python
# 从共享模块 re-export，保持旧 import 路径兼容（trpg_dice/trpg_session 仍引用）
from core.trpg.rules import (  # noqa: F401
    ATTRIBUTES, ATTRIBUTE_EN, SKILLS, SKILL_ALIASES, RACES, CLASSES,
    POINT_BUY_COST, POINT_BUY_BUDGET, STANDARD_ARRAY,
    ability_modifier, skill_attribute, race_bonuses, class_info,
)
```

- [ ] **Step 3: 将 `plugins/trpg_char/character.py` 改为 re-export**

```python
# 从共享模块 re-export，保持旧 import 路径兼容（trpg_dice/trpg_session 仍引用）
from core.trpg.character import (  # noqa: F401
    finalize,
    get_attr_value,
    resolve_expression_values,
    format_sheet,
)
```

- [ ] **Step 4: 回归测试**

Run: `python test/test_trpg.py`
Expected: 全部 PASS（骰子插件经 `plugins.trpg_char.character` re-export 访问，行为不变）

- [ ] **Step 5: Commit**

```bash
git add core/trpg/ plugins/trpg_char/rules.py plugins/trpg_char/character.py
git commit -m "refactor(跑团): 迁移 DND 规则计算模块到 core/trpg 共享位置"
```

---

### Task 2: 新增 `core/character_store.py` 角色 JSON 存储层

**Files:**
- Create: `core/character_store.py`
- Test: `test/test_character_store.py`

**Interfaces:**
- Consumes: 无（纯 stdlib）
- Produces:
  - `CHARS_ROOT: Path`（模块级可替换，默认 `Path("server_data/trpg_chars")`，支持 `BOTERO_TRPG_CHARS_ROOT` env）
  - `list_chars(user_id) -> list[dict]`（按 meta.order 顺序返回完整角色 dict）
  - `get_char(user_id, char_id) -> dict | None`（含 `id`/`user_id` 字段）
  - `get_current(user_id) -> dict | None`
  - `create_char(user_id, data: dict) -> int`（id 自增；首个角色自动设为当前）
  - `update_char(user_id, char_id, data: dict) -> None`（整卡替换；不存在 raise ValueError）
  - `delete_char(user_id, char_id) -> None`（删除当前角色则自动切下一个）
  - `set_current(user_id, char_id) -> None`（不存在 raise ValueError）

**存储格式：**
```
server_data/trpg_chars/<user_id>/meta.json        # {"current_id": 3, "order": [1,2,3]}
server_data/trpg_chars/<user_id>/<char_id>.json   # 完整角色 dict
```

- [ ] **Step 1: 写失败测试 `test/test_character_store.py`**

```python
"""测试 core.character_store 角色 JSON 存储层。

运行: python test/test_character_store.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import character_store as store


def _base_data() -> dict:
    return {
        "char_name": "艾伦", "race": "精灵", "class_name": "法师",
        "level": 1, "background": "", "str_score": 8, "dex_score": 14,
        "con_score": 12, "int_score": 15, "wis_score": 13, "cha_score": 10,
        "proficient_skills": ["奥术"], "hp": 0, "ac": 0, "notes": "",
    }


class CharacterStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(store, "CHARS_ROOT", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_create_and_get(self):
        cid = store.create_char("123", _base_data())
        got = store.get_char("123", cid)
        self.assertEqual(got["char_name"], "艾伦")
        self.assertEqual(got["id"], cid)
        self.assertIsNone(store.get_char("456", cid))  # 跨用户不可见

    def test_create_first_auto_current(self):
        cid = store.create_char("123", _base_data())
        self.assertEqual(store.get_current("123")["id"], cid)

    def test_list_order_and_set_current(self):
        c1 = store.create_char("123", _base_data())
        c2 = store.create_char("123", _base_data())
        ids = [c["id"] for c in store.list_chars("123")]
        self.assertEqual(ids, [c1, c2])
        store.set_current("123", c1)
        self.assertEqual(store.get_current("123")["id"], c1)

    def test_delete_current_switches_to_next(self):
        c1 = store.create_char("123", _base_data())
        c2 = store.create_char("123", _base_data())
        store.delete_char("123", c1)
        self.assertEqual(store.get_current("123")["id"], c2)
        store.delete_char("123", c2)
        self.assertIsNone(store.get_current("123"))
        self.assertEqual(store.list_chars("123"), [])

    def test_update_replaces_data(self):
        cid = store.create_char("123", _base_data())
        data = _base_data()
        data["char_name"] = "改名"
        store.update_char("123", cid, data)
        self.assertEqual(store.get_char("123", cid)["char_name"], "改名")

    def test_rejects_bad_ids(self):
        with self.assertRaises(ValueError):
            store.create_char("abc", _base_data())
        with self.assertRaises(ValueError):
            store.create_char("1.5", _base_data())
        cid = store.create_char("123", _base_data())
        with self.assertRaises(ValueError):
            store.update_char("123", f"{cid}x", _base_data())
        with self.assertRaises(ValueError):
            store.set_current("123", "999")  # 不存在的角色

    def test_meta_order_after_delete(self):
        c1 = store.create_char("123", _base_data())
        c2 = store.create_char("123", _base_data())
        store.delete_char("123", c1)
        meta = json.loads((store.CHARS_ROOT / "123" / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["order"], [c2])
        self.assertEqual(meta["current_id"], c2)

    def test_atomic_write_leaves_no_tmp(self):
        cid = store.create_char("123", _base_data())
        leftovers = list((store.CHARS_ROOT / "123").glob("*.tmp"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python test/test_character_store.py`
Expected: FAIL（`ImportError: cannot import name 'character_store'`）

- [ ] **Step 3: 实现 `core/character_store.py`**

```python
"""角色卡 JSON 文件存储层（bot 与 web 双进程共用）。

存储布局：
    server_data/trpg_chars/<user_id>/meta.json        # {"current_id": 3, "order": [1,2,3]}
    server_data/trpg_chars/<user_id>/<char_id>.json   # 单个角色完整数据（任意嵌套 dict）

所有写入均为原子写（tmp + os.replace），跨进程并发安全。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CHARS_ROOT = Path(os.environ.get("BOTERO_TRPG_CHARS_ROOT", "server_data/trpg_chars"))


def _validate_user_id(user_id) -> str:
    uid = str(user_id).strip()
    if not uid.isdigit():
        raise ValueError(f"非法用户 ID: {user_id!r}")
    return uid


def _validate_char_id(char_id) -> int:
    try:
        cid = int(char_id)
    except (TypeError, ValueError):
        raise ValueError(f"非法角色 ID: {char_id!r}") from None
    if cid <= 0:
        raise ValueError(f"非法角色 ID: {char_id!r}")
    return cid


def _user_dir(user_id) -> Path:
    return CHARS_ROOT / _validate_user_id(user_id)


def _char_path(user_id, char_id) -> Path:
    return _user_dir(user_id) / str(_validate_char_id(char_id))


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_meta(user_id) -> dict:
    meta = _read_json(_user_dir(user_id) / "meta.json")
    meta.setdefault("current_id", None)
    meta.setdefault("order", [])
    return meta


def _save_meta(user_id, meta: dict) -> None:
    _write_json(_user_dir(user_id) / "meta.json", meta)


def list_chars(user_id) -> list[dict]:
    meta = _load_meta(user_id)
    out = []
    for cid in meta["order"]:
        data = get_char(user_id, cid)
        if data:
            out.append(data)
    return out


def get_char(user_id, char_id) -> dict | None:
    path = _char_path(user_id, char_id)
    if not path.is_file():
        return None
    data = _read_json(path)
    if not data:
        return None
    data["id"] = _validate_char_id(char_id)
    data["user_id"] = _validate_user_id(user_id)
    return data


def get_current(user_id) -> dict | None:
    cid = _load_meta(user_id)["current_id"]
    return get_char(user_id, cid) if cid is not None else None


def create_char(user_id, data: dict) -> int:
    uid = _validate_user_id(user_id)
    meta = _load_meta(uid)
    next_id = max(meta["order"], default=0) + 1
    meta["order"].append(next_id)
    if meta["current_id"] is None:
        meta["current_id"] = next_id
    _write_json(_char_path(uid, next_id), data)
    _save_meta(uid, meta)
    return next_id


def update_char(user_id, char_id, data: dict) -> None:
    path = _char_path(user_id, char_id)
    if not path.is_file():
        raise ValueError("角色不存在")
    _write_json(path, data)


def delete_char(user_id, char_id) -> None:
    uid = _validate_user_id(user_id)
    cid = _validate_char_id(char_id)
    path = _char_path(uid, cid)
    if path.is_file():
        path.unlink()
    meta = _load_meta(uid)
    if cid in meta["order"]:
        meta["order"].remove(cid)
    if meta["current_id"] == cid:
        meta["current_id"] = meta["order"][0] if meta["order"] else None
        if meta["current_id"] is None:
            meta.pop("current_id", None)
    _save_meta(uid, meta)


def set_current(user_id, char_id) -> None:
    uid = _validate_user_id(user_id)
    cid = _validate_char_id(char_id)
    if not _char_path(uid, cid).is_file():
        raise ValueError("角色不存在")
    meta = _load_meta(uid)
    meta["current_id"] = cid
    _save_meta(uid, meta)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python test/test_character_store.py`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/character_store.py test/test_character_store.py
git commit -m "feat(跑团): 新增角色卡 JSON 文件存储层"
```

---

### Task 3: 新增 `core/user_settings.py` 通用个人设置模块

**Files:**
- Create: `core/user_settings.py`
- Test: `test/test_user_settings.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `SETTINGS_ROOT: Path`（模块级可替换，默认 `Path("server_data/user_settings")`，支持 `BOTERO_USER_SETTINGS_ROOT` env）
  - `get_settings(user_id) -> dict`（文件不存在返回 `{}`）
  - `update_settings(user_id, patch: dict) -> dict`（深合并后原子写，返回最新完整 dict）
  - `privacy_public(user_id) -> bool`（读 `privacy.char_public`，缺省 True）

- [ ] **Step 1: 写失败测试 `test/test_user_settings.py`**

```python
"""测试 core.user_settings 通用个人设置模块。

运行: python test/test_user_settings.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import user_settings as us


class UserSettingsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(us, "SETTINGS_ROOT", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_default_empty(self):
        self.assertEqual(us.get_settings("123"), {})

    def test_default_privacy_public(self):
        self.assertTrue(us.privacy_public("123"))

    def test_update_and_get(self):
        us.update_settings("123", {"privacy": {"char_public": False}})
        self.assertEqual(us.get_settings("123"), {"privacy": {"char_public": False}})
        self.assertFalse(us.privacy_public("123"))

    def test_deep_merge_keeps_other_keys(self):
        us.update_settings("123", {"privacy": {"char_public": False}})
        us.update_settings("123", {"other_feature": {"flag": True}})
        settings = us.get_settings("123")
        self.assertEqual(settings["privacy"], {"char_public": False})
        self.assertEqual(settings["other_feature"], {"flag": True})

    def test_update_overwrites_scalar(self):
        us.update_settings("123", {"privacy": {"char_public": True}})
        us.update_settings("123", {"privacy": {"char_public": False}})
        self.assertFalse(us.privacy_public("123"))

    def test_isolated_between_users(self):
        us.update_settings("123", {"privacy": {"char_public": False}})
        self.assertTrue(us.privacy_public("456"))

    def test_rejects_bad_user_id(self):
        with self.assertRaises(ValueError):
            us.update_settings("../evil", {"a": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python test/test_user_settings.py`
Expected: FAIL

- [ ] **Step 3: 实现 `core/user_settings.py`**

```python
"""通用个人设置存储层（绑定 QQ 号，bot 与 web 双进程共用）。

每用户一个 JSON 文件：server_data/user_settings/<user_id>.json
文件不存在 = 全默认值。各功能自行约定键名，深合并写入。

已约定键：
    privacy.char_public: bool  是否允许他人查看我的角色卡（缺省 True）
"""

from __future__ import annotations

import json
import os
from pathlib import Path

SETTINGS_ROOT = Path(os.environ.get("BOTERO_USER_SETTINGS_ROOT", "server_data/user_settings"))


def _settings_path(user_id) -> Path:
    uid = str(user_id).strip()
    if not uid.isdigit():
        raise ValueError(f"非法用户 ID: {user_id!r}")
    return SETTINGS_ROOT / uid


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def get_settings(user_id) -> dict:
    return _read(_settings_path(user_id))


def update_settings(user_id, patch: dict) -> dict:
    path = _settings_path(user_id)
    merged = _deep_merge(_read(path), patch)
    _write(path, merged)
    return merged


def privacy_public(user_id) -> bool:
    return bool(get_settings(user_id).get("privacy", {}).get("char_public", True))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python test/test_user_settings.py`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/user_settings.py test/test_user_settings.py
git commit -m "feat(设置): 新增通用个人设置 JSON 存储层"
```

---

### Task 4: 精简 QQ 端 `plugins/trpg_char`

**Files:**
- Modify: `plugins/trpg_char/__init__.py`（重写：删创建/编辑/向导，查看仅自己，存储层切换）
- Delete: `plugins/trpg_char/wizard.py`
- Modify: `core/context.py`（删除 `character_wizards` 定义）
- Test: `test/test_trpg_char.py`（现有，需同步）

**Interfaces:**
- Consumes: `core.character_store`（Task 2）、`core.trpg.character.format_sheet`（Task 1）
- Produces: `/角色` 命令新语义

**命令变更：**

| 指令 | 新行为 |
|------|--------|
| `/角色` / `/角色 查看` | 查看**自己的**当前角色卡（忽略 @，不再支持查看他人） |
| `/角色 列表` | 列出我的角色（同旧逻辑） |
| `/角色 切换 <编号>` | 同旧逻辑 |
| `/角色 删除 <编号>` | 同旧逻辑 |
| `/角色 创建` / `/角色 编辑 …` / `/角色 放弃` | 回复引导到网页端 |

- [ ] **Step 1: 确认 `character_wizards` 引用范围**

```bash
grep -rn "character_wizards" core/ plugins/ | grep -v __pycache__
```

Expected: 仅 `core/context.py` 定义 + `plugins/trpg_char/__init__.py` 引用

- [ ] **Step 2: 重写 `plugins/trpg_char/__init__.py`**

```python
from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from core import character_store as store
from . import character as char_logic

WEB_TRPG_URL = "http://127.0.0.1:8765/profile/trpg"


@register_plugin
class TrpgCharPlugin(Plugin):
    name = "trpg_char"
    description = "DND 5E 角色卡：查看/列表/切换/删除（创建与编辑请到网页端）"

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def match(self, message_type) -> bool:
        if message_type != "message":
            return False
        return self._first_text().startswith("/角色")

    def handle(self):
        try:
            msg = self._first_text()
            if msg.startswith("/角色"):
                self._route_command(msg)
        except Exception:
            logger.exception("TrpgChar 处理异常")

    def _route_command(self, msg: str):
        parts = msg.split()
        sub = parts[1] if len(parts) > 1 else ""
        if sub in ("创建", "编辑", "放弃"):
            self.api.send_msg(text(
                "角色卡的创建与编辑已迁移到网页端：\n" + WEB_TRPG_URL
            ))
        elif sub == "切换":
            self._handle_switch(parts[2:])
        elif sub == "删除":
            self._handle_delete(parts[2:])
        elif sub == "列表":
            self._handle_list()
        else:
            self._handle_view()

    def _handle_view(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        char_data = store.get_current(user_id)
        if not char_data:
            self.api.send_msg(text("你还没有角色卡，请到网页端创建：\n" + WEB_TRPG_URL))
            return
        self.api.send_msg(text(char_logic.format_sheet(char_data)))

    def _handle_list(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        chars = store.list_chars(user_id)
        if not chars:
            self.api.send_msg(text("你还没有角色卡，请到网页端创建：\n" + WEB_TRPG_URL))
            return
        current = store.get_current(user_id)
        current_id = current["id"] if current else None
        lines = ["你的角色卡："]
        for c in chars:
            mark = " ◀ 当前" if c["id"] == current_id else ""
            lines.append(f"#{c['id']} {c['char_name']} Lv.{c['level']} {c['race']} {c['class_name']}{mark}")
        self.api.send_msg(text("\n".join(lines)))

    def _handle_switch(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if not args or not args[0].lstrip("#").isdigit():
            self.api.send_msg(text("格式：/角色 切换 <编号>"))
            return
        char_id = int(args[0].lstrip("#"))
        try:
            store.set_current(user_id, char_id)
        except ValueError:
            self.api.send_msg(text("角色不存在"))
            return
        char = store.get_char(user_id, char_id)
        self.api.send_msg(text(f"已将当前角色切换为 {char['char_name']}"))

    def _handle_delete(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if not args or not args[0].lstrip("#").isdigit():
            self.api.send_msg(text("格式：/角色 删除 <编号>"))
            return
        char_id = int(args[0].lstrip("#"))
        char = store.get_char(user_id, char_id)
        if not char:
            self.api.send_msg(text("角色不存在"))
            return
        store.delete_char(user_id, char_id)
        self.api.send_msg(text(f"已删除角色 {char['char_name']}"))
```

- [ ] **Step 3: 删除 `wizard.py`、清理 `core/context.py`**

```bash
git rm plugins/trpg_char/wizard.py
```

在 `core/context.py` 中删除 `character_wizards = {}` 的定义行及其上方注释（先读文件确认行号，删除后确保无其他引用）。

- [ ] **Step 4: 更新 `test/test_trpg_char.py`**

先读现有文件确认用例清单。删除/替换规则：
- 删除：向导相关（`_handle_wizard_reply` 流程）、`创建`、`编辑`、`@查看他人` 的用例
- 替换：`查看` 用例改为断言仅返回自己的当前角色卡；`列表/切换/删除` 用例的 mock 从 `self.dbmanager.character` 改为 patch `core.character_store`（注意：插件内 `from core import character_store as store`，patch 目标是 `core.character_store.list_chars` 等函数本身）
- 新增用例：`创建` 回复包含 `/profile/trpg`

示例（查看用例替换）：

```python
class TestTrpgCharView(TestCase):
    def test_view_own_current(self):
        ctx = make_private_message("/角色 查看")
        plugin = TrpgCharPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        with patch("core.character_store.get_current", return_value=_base_data()):
            plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("【艾伦】", out)

    def test_view_without_char(self):
        ctx = make_private_message("/角色 查看")
        plugin = TrpgCharPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        with patch("core.character_store.get_current", return_value=None):
            plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("/profile/trpg", out)

    def test_create_redirects_to_web(self):
        ctx = make_private_message("/角色 创建")
        plugin = TrpgCharPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("/profile/trpg", out)
```

（`make_private_message` / `_base_data` 若 test 文件中没有，则按现有 `make_group_message` 的写法在测试内定义；以实际文件为准。）

- [ ] **Step 5: 运行测试确认通过**

Run: `python test/test_trpg_char.py` 且 `python test/test_trpg.py`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add plugins/trpg_char/ core/context.py test/test_trpg_char.py
git commit -m "feat(跑团): QQ 端角色命令精简为查看/列表/切换/删除，创建编辑引导至网页端"
```

---

### Task 5: 适配 `trpg_dice` 与 `trpg_session` 到新存储层

**Files:**
- Modify: `plugins/trpg_dice/__init__.py:96-120`（`_resolve_character_expr`）
- Modify: `plugins/trpg_session/__init__.py:264-278`（导出时取角色名）
- Test: `test/test_trpg.py`（回归）

**Interfaces:**
- Consumes: `core.character_store.get_current`（Task 2）
- Produces: 无新接口

- [ ] **Step 1: 修改 `plugins/trpg_dice/__init__.py` 的 `_resolve_character_expr`**

将 `self.dbmanager.character.current(user_id)`（原第 109 行）替换为 `store.get_current(user_id)`，并在文件顶部加入 `from core import character_store as store`（原第 98-99 行对 `plugins.trpg_char.character/rules` 的 import 保持不变，re-export 兼容）：

```python
def _resolve_character_expr(self, expr: str):
    """若表达式含角色属性/技能名，替换为数值。返回 (解析后表达式, 显示用原式) 或 (None, None)。"""
    from plugins.trpg_char.character import resolve_expression_values
    from plugins.trpg_char.rules import ATTRIBUTES, SKILLS, SKILL_ALIASES

    names = [n for n in list(ATTRIBUTES) + list(SKILLS) if n in expr]
    aliases = [a for a in SKILL_ALIASES if a in expr]
    if not names and not aliases:
        return expr, expr

    user_id = self.bot_event.user_id
    if user_id is None:
        return None, None
    char = store.get_current(user_id)
    if not char:
        self.api.send_msg(text("你还没有角色卡，请到网页端创建：\nhttp://127.0.0.1:8765/profile/trpg"))
        return None, None

    values = resolve_expression_values(char)
    resolved = expr
    for name in sorted(values, key=len, reverse=True):
        resolved = resolved.replace(name, str(values[name]))
    for alias in aliases:
        resolved = resolved.replace(alias, str(values[SKILL_ALIASES[alias]]))
    return resolved, expr
```

- [ ] **Step 2: 修改 `plugins/trpg_session/__init__.py` 导出逻辑**

将 `char_cache[uid] = self.dbmanager.character.current(uid)`（原第 273 行）替换为：

```python
char_cache[uid] = store.get_current(uid)
```

并在文件顶部（其他 `from core...` import 之后）加入 `from core import character_store as store`。

- [ ] **Step 3: 全局搜索残留的 `dbmanager.character`**

```bash
grep -rn "dbmanager.character" plugins/ core/ | grep -v __pycache__
```

Expected: 无输出（若仍有引用则一并替换为 store 对应调用）

- [ ] **Step 4: 回归测试**

Run: `python test/test_trpg.py`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/trpg_dice/__init__.py plugins/trpg_session/__init__.py
git commit -m "refactor(跑团): 骰子与跑团记录切换至角色 JSON 存储层"
```

---

### Task 6: 删除 SQLite 角色表与 `CharacterManager`

**Files:**
- Delete: `core/db/character.py`
- Modify: `core/db/_base.py`（删除两张建表语句 + ALTER 兼容代码）
- Modify: `core/database_manager.py`（删除 import 与 `self.character` 赋值）
- Test: `python -c "from core.database_manager import DbManager; DbManager()"` 冒烟

- [ ] **Step 1: 删除建表语句与兼容代码**

在 `core/db/_base.py` 中删除第 306-332 行整块（`dnd_characters` 建表、`dnd_current_character` 建表、`PRAGMA table_info(dnd_characters)` 兼容检查）：

```python
    # 整块删除以下内容（原 306-332 行）：
    # cur.execute("""CREATE TABLE IF NOT EXISTS dnd_characters (...""")
    # cur.execute("""CREATE TABLE IF NOT EXISTS dnd_current_character (...""")
    # cur.execute("PRAGMA table_info(dnd_characters)")
    # _char_cols = ...
    # if "notes" not in _char_cols: ...
```

- [ ] **Step 2: 修改 `core/database_manager.py`**

删除第 13 行 `from core.db.character import CharacterManager` 与第 32 行 `self.character = CharacterManager(self.conn)`。

- [ ] **Step 3: 删除 `core/db/character.py`**

```bash
git rm core/db/character.py
```

- [ ] **Step 4: 冒烟测试**

Run: `python -c "from core.database_manager import DbManager; DbManager(); print('ok')"`
Expected: 输出 `ok`，无 ImportError

- [ ] **Step 5: Commit**

```bash
git add -A core/db/ core/database_manager.py
git commit -m "refactor(跑团): 弃用 SQLite 角色卡表，存储全面切换至 JSON 文件"
```

---

### Task 7: 后端 API 端点（`checkin_gallery/app.py` + `checkin_gallery/config.py`）

**Files:**
- Modify: `checkin_gallery/config.py`（新增路径常量）
- Modify: `checkin_gallery/app.py`（新增车卡/设置/规则端点 + 页面路由）

**Interfaces:**
- Consumes: `core.character_store`（Task 2）、`core.user_settings`（Task 3）、`core.trpg.character.finalize`、`core.trpg.rules`（Task 1）
- Produces: 前端页面依赖的 API（Task 8/9/10）

**端点清单：**

| 方法/路径 | 鉴权 | 说明 |
|-----------|------|------|
| `GET /api/me/characters` | 登录 | 我的角色列表（含 current_id 标记、每张卡 finalize 后的计算值） |
| `POST /api/me/characters` | 登录 | 创建（body=完整角色 JSON，finalize 重算后落盘） |
| `GET /api/me/characters/{char_id}` | 登录 | 取单张卡（本人） |
| `PUT /api/me/characters/{char_id}` | 登录 | 全量保存（finalize 重算后落盘） |
| `DELETE /api/me/characters/{char_id}` | 登录 | 删除 |
| `POST /api/me/characters/{char_id}/activate` | 登录 | 设为当前角色 |
| `GET /api/characters/{user_id}/{char_id}` | 登录 | 查看任意用户角色卡（目标 `char_public=false` → 403） |
| `GET /api/trpg/rules` | 免登录 | 规则数据（前端实时计算用） |
| `GET /api/me/settings` | 登录 | 返回 `{"privacy": {"char_public": bool}}` |
| `PUT /api/me/settings` | 登录 | body 深合并写入 |

- [ ] **Step 1: `checkin_gallery/config.py` 增加路径常量**

```python
TRPG_CHARS_ROOT = _path_from_env(
    "BOTERO_TRPG_CHARS_ROOT", PROJECT_ROOT / "server_data" / "trpg_chars"
)
USER_SETTINGS_ROOT = _path_from_env(
    "BOTERO_USER_SETTINGS_ROOT", PROJECT_ROOT / "server_data" / "user_settings"
)
```

注意：`core/character_store.py` 的 `CHARS_ROOT` 默认值是**相对路径** `server_data/trpg_chars`（bot 进程 cwd=项目根）；web 进程 cwd 也是项目根（`python -m checkin_gallery`），两者一致，无需把 config 常量传入 core 模块。

- [ ] **Step 2: 在 `checkin_gallery/app.py` 顶部增加 import**

```python
from core import character_store as char_store
from core import user_settings as user_settings_mod
from core.trpg import character as trpg_char
from core.trpg import rules as trpg_rules
```

- [ ] **Step 3: 新增 Pydantic 模型与校验函数**

```python
class CharacterIn(BaseModel):
    char_name: str
    race: str
    class_name: str
    level: int = 1
    background: str = ""
    str_score: int
    dex_score: int
    con_score: int
    int_score: int
    wis_score: int
    cha_score: int
    proficient_skills: list[str] = []
    hp: int = 0
    ac: int = 0
    equipment: list = []
    notes: str = ""


class SettingsIn(BaseModel):
    privacy: dict | None = None


class SettingsOut(BaseModel):
    privacy: dict


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
    proficient_skills: list[str]
    notes: str


def _char_to_out(data: dict) -> CharOut:
    finalized = trpg_char.finalize(data)
    return CharOut(
        id=data["id"],
        user_id=data["user_id"],
        display_name=resolve_display_name(data["user_id"]),
        char_name=finalized["char_name"],
        race=finalized.get("race", ""),
        class_name=finalized.get("class_name", ""),
        level=int(finalized.get("level", 1)),
        hp=finalized["hp"],
        ac=finalized["ac"],
        skill_mods=finalized.get("skill_mods", {}),
        scores=finalized.get("scores", {}),
        proficient_skills=finalized.get("proficient_skills", []),
        notes=finalized.get("notes", ""),
    )
```

- [ ] **Step 4: 新增车卡端点**

```python
@app.get("/api/me/characters")
def api_my_characters(user_id: Annotated[str, Depends(get_current_user_id)]):
    chars = char_store.list_chars(user_id)
    current = char_store.get_current(user_id)
    current_id = current["id"] if current else None
    return {
        "current_id": current_id,
        "characters": [_char_to_out(c) for c in chars],
    }


@app.post("/api/me/characters", response_model=CharOut)
def api_create_character(
    body: CharacterIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    data = body.model_dump()
    finalized = trpg_char.finalize(data)
    data["hp"] = finalized["hp"]
    data["ac"] = finalized["ac"]
    try:
        char_id = char_store.create_char(user_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _char_to_out(char_store.get_char(user_id, char_id))


@app.get("/api/me/characters/{char_id}", response_model=CharOut)
def api_get_my_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    char = char_store.get_char(user_id, char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _char_to_out(char)


@app.put("/api/me/characters/{char_id}", response_model=CharOut)
def api_update_character(
    char_id: int,
    body: CharacterIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not char_store.get_char(user_id, char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    data = body.model_dump()
    finalized = trpg_char.finalize(data)
    data["hp"] = finalized["hp"]
    data["ac"] = finalized["ac"]
    try:
        char_store.update_char(user_id, char_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _char_to_out(char_store.get_char(user_id, char_id))


@app.delete("/api/me/characters/{char_id}")
def api_delete_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not char_store.get_char(user_id, char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    char_store.delete_char(user_id, char_id)
    return {"ok": True}


@app.post("/api/me/characters/{char_id}/activate")
def api_activate_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        char_store.set_current(user_id, char_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/characters/{user_id}/{char_id}", response_model=CharOut)
def api_view_character(
    user_id: str,
    char_id: int,
    viewer_id: Annotated[str, Depends(get_current_user_id)],
):
    if not str(user_id).isdigit():
        raise HTTPException(status_code=400, detail="非法用户 ID")
    if str(viewer_id) != str(user_id) and not user_settings_mod.privacy_public(user_id):
        raise HTTPException(status_code=403, detail="对方未公开角色卡")
    try:
        char = char_store.get_char(user_id, char_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _char_to_out(char)


@app.get("/api/trpg/rules")
def api_trpg_rules():
    return {
        "attributes": trpg_rules.ATTRIBUTES,
        "attribute_en": trpg_rules.ATTRIBUTE_EN,
        "skills": trpg_rules.SKILLS,
        "skill_aliases": trpg_rules.SKILL_ALIASES,
        "races": trpg_rules.RACES,
        "classes": trpg_rules.CLASSES,
        "point_buy_cost": trpg_rules.POINT_BUY_COST,
        "point_buy_budget": trpg_rules.POINT_BUY_BUDGET,
        "standard_array": trpg_rules.STANDARD_ARRAY,
    }
```

注意：`api_view_character` 的路径参数 `user_id` 是字符串，可能含非法字符——函数内已做 `.isdigit()` 前置校验与 `ValueError` 捕获。

- [ ] **Step 5: 新增设置端点**

```python
@app.get("/api/me/settings", response_model=SettingsOut)
def api_my_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    settings = user_settings_mod.get_settings(user_id)
    return SettingsOut(privacy=settings.get("privacy", {}))


@app.put("/api/me/settings", response_model=SettingsOut)
def api_update_settings(
    body: SettingsIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    patch = body.model_dump(exclude_none=True)
    merged = user_settings_mod.update_settings(user_id, patch)
    return SettingsOut(privacy=merged.get("privacy", {}))
```

- [ ] **Step 6: 新增页面路由**

```python
@app.get("/profile/trpg")
def profile_trpg_page():
    page = STATIC_DIR / "trpg.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少跑团车卡页")
    return FileResponse(page)


@app.get("/trpg/char/{user_id}/{char_id}")
def trpg_char_view_page(user_id: str, char_id: int):
    page = STATIC_DIR / "char_view.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少角色卡查看页")
    return FileResponse(page)
```

- [ ] **Step 7: 启动冒烟验证**

```bash
python -m checkin_gallery 2>&1 &
sleep 2
curl -s http://127.0.0.1:8765/api/trpg/rules | head -c 200
kill %1
```

Expected: 输出 JSON 片段（`{"attributes": ...`），无异常日志

- [ ] **Step 8: Commit**

```bash
git add checkin_gallery/config.py checkin_gallery/app.py
git commit -m "feat(网页): 新增车卡/设置/规则 API 端点与页面路由"
```

---

### Task 8: 前端车卡管理页（`trpg.html` + `trpg.js`）

**Files:**
- Create: `checkin_gallery/static/trpg.html`
- Create: `checkin_gallery/static/trpg.js`
- Modify: `checkin_gallery/static/profile.css`（编辑器分区样式，追加到文件末尾）

**Interfaces:**
- Consumes: `GET/POST/PUT/DELETE /api/me/characters*`、`POST /api/me/characters/{id}/activate`、`GET /api/trpg/rules`、`GalleryAuth`（`auth.js`）
- Produces: 无（页面）

**页面结构（`trpg.html`，沿用 profile 系列模板）：**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>跑团车卡 · 打卡图库</title>
  <link rel="stylesheet" href="/static/gallery.css" />
  <link rel="stylesheet" href="/static/profile.css" />
</head>
<body>
  <header class="toolbar profile-toolbar">
    <a href="/" class="back-link">← 图库</a>
    <nav class="profile-nav">
      <a href="/profile">主页</a>
      <a href="/profile/checkin">打卡</a>
      <a href="/profile/shop">商店</a>
      <a href="/profile/alarms">闹钟</a>
      <a href="/profile/trpg" class="active">跑团</a>
      <a href="/guestbook">留言簿</a>
      <a href="/profile/settings">设置</a>
    </nav>
    <div class="auth-area" id="authArea"></div>
  </header>

  <main class="profile-main" id="trpgMain">
    <p class="loading-msg">加载中…</p>
  </main>

  <script src="/static/auth.js"></script>
  <script src="/static/trpg.js"></script>
</body>
</html>
```

**`trpg.js` 核心结构（完整实现）：**

```javascript
const trpgMain = document.getElementById("trpgMain");

let rules = null;        // /api/trpg/rules 数据
let chars = [];          // 我的角色列表
let currentId = null;    // 当前角色 id
let editing = null;      // 正在编辑的角色数据（null = 新建）

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    window.location.href = "/";
    return false;
  }
  return true;
}

function renderAuthChip() {
  const session = GalleryAuth.load();
  const area = document.getElementById("authArea");
  if (!session) return;
  area.innerHTML = "";
  const link = document.createElement("a");
  link.className = "user-chip";
  link.href = "/profile";
  const img = document.createElement("img");
  img.src = session.avatar_url || "";
  img.alt = session.display_name;
  img.onerror = () => { img.style.display = "none"; };
  const wrap = document.createElement("span");
  wrap.innerHTML = `<strong>${escapeHtml(session.display_name)}</strong><br><span class="uid">${session.user_id}</span>`;
  link.append(img, wrap);
  area.appendChild(link);
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...GalleryAuth.headers(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    GalleryAuth.clear();
    window.location.href = "/";
    throw new Error("未登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "操作失败");
  return data;
}

function showToast(msg, isError = false) {
  let toast = document.getElementById("trpgToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "trpgToast";
    toast.className = "settings-toast";
    trpgMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 2800);
}

// ── 计算（与后端 core/trpg/character.finalize 口径一致）──

function abilityMod(score) {
  return Math.floor((Number(score || 8) - 10) / 2);
}

function attrKey(name) {
  return { "力量": "str_score", "敏捷": "dex_score", "体质": "con_score",
           "智力": "int_score", "感知": "wis_score", "魅力": "cha_score" }[name] || "";
}

function computeSheet(data) {
  const scores = {};
  for (const attr of rules.attributes) {
    const key = attrKey(attr);
    const base = Number(data[key] ?? 8) + (rules.races[data.race]?.[attr] || 0);
    scores[key] = base;
  }
  const conMod = abilityMod(scores.con_score);
  const dexMod = abilityMod(scores.dex_score);
  const hpDie = rules.classes[data.class_name]?.hp_die || 8;
  const skillMods = {};
  for (const [skill, attr] of Object.entries(rules.skills)) {
    let mod = abilityMod(scores[attrKey(attr)]);
    if ((data.proficient_skills || []).includes(skill)) mod += 2;
    skillMods[skill] = mod;
  }
  return {
    scores, skillMods,
    hp: Number(data.hp) || hpDie + conMod,
    ac: Number(data.ac) || 10 + dexMod,
    hpDie,
  };
}

// ── 视图：列表 ──

function renderList() {
  trpgMain.innerHTML = "";
  const head = document.createElement("div");
  head.className = "section-head";
  head.innerHTML = `<h2>我的角色卡</h2>`;
  const newBtn = document.createElement("button");
  newBtn.type = "button";
  newBtn.className = "btn-sm primary";
  newBtn.textContent = "新建角色";
  newBtn.addEventListener("click", () => {
    editing = {
      char_name: "", race: "人类", class_name: "战士", level: 1, background: "",
      str_score: 10, dex_score: 10, con_score: 10, int_score: 10, wis_score: 10, cha_score: 10,
      proficient_skills: [], hp: 0, ac: 0, equipment: [], notes: "",
    };
    renderEditor();
  });
  head.appendChild(newBtn);
  trpgMain.appendChild(head);

  if (!chars.length) {
    const p = document.createElement("p");
    p.className = "empty-hint";
    p.textContent = "还没有角色卡，点击右上角「新建角色」开始车卡";
    trpgMain.appendChild(p);
    return;
  }

  for (const c of chars) {
    const row = document.createElement("article");
    row.className = "settings-title-row";
    const isCur = c.id === currentId;
    row.innerHTML = `
      <div class="row-main">
        <strong>[#${c.id}] ${escapeHtml(c.char_name)}${isCur ? " ◀ 当前" : ""}</strong>
        <span class="rarity">Lv.${c.level} ${escapeHtml(c.race)} ${escapeHtml(c.class_name)}</span>
        <p class="desc">HP ${c.hp} / AC ${c.ac}</p>
      </div>
    `;
    const actions = document.createElement("div");
    actions.className = "row-actions";
    const actBtn = document.createElement("button");
    actBtn.type = "button";
    actBtn.className = "btn-sm";
    actBtn.textContent = "查看";
    actBtn.addEventListener("click", () => { window.location.href = `/trpg/char/${c.user_id}/${c.id}`; });
    actions.appendChild(actBtn);
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn-sm";
    editBtn.textContent = "编辑";
    editBtn.addEventListener("click", async () => {
      try {
        editing = await apiFetch(`/api/me/characters/${c.id}`);
        renderEditor();
      } catch (err) { showToast(err.message, true); }
    });
    actions.appendChild(editBtn);
    if (!isCur) {
      const swBtn = document.createElement("button");
      swBtn.type = "button";
      swBtn.className = "btn-sm";
      swBtn.textContent = "设为当前";
      swBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/me/characters/${c.id}/activate`, { method: "POST" });
          await loadList();
          showToast("已设为当前角色");
        } catch (err) { showToast(err.message, true); }
      });
      actions.appendChild(swBtn);
    }
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn-sm danger";
    delBtn.textContent = "删除";
    delBtn.addEventListener("click", async () => {
      if (!confirm(`确定删除角色「${c.char_name}」？`)) return;
      try {
        await apiFetch(`/api/me/characters/${c.id}`, { method: "DELETE" });
        await loadList();
        showToast("已删除角色");
      } catch (err) { showToast(err.message, true); }
    });
    actions.appendChild(delBtn);
    row.appendChild(actions);
    trpgMain.appendChild(row);
  }
}

// ── 视图：编辑器（单页分区表格）──

function renderEditor() {
  trpgMain.innerHTML = "";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "btn-sm";
  back.textContent = "← 返回列表";
  back.addEventListener("click", () => renderList());
  trpgMain.appendChild(back);

  const form = document.createElement("div");
  form.className = "trpg-editor";
  form.innerHTML = `
    <section class="settings-section">
      <div class="section-head"><h2>基本信息</h2></div>
      <table class="trpg-table">
        <tr><th>角色名</th><td><input type="text" data-f="char_name" maxlength="30"></td>
            <th>种族</th><td><input type="text" data-f="race" list="raceList"></td></tr>
        <tr><th>职业</th><td><input type="text" data-f="class_name" list="classList"></td>
            <th>等级</th><td><input type="number" data-f="level" min="1" max="20"></td></tr>
        <tr><th>背景</th><td colspan="3"><input type="text" data-f="background"></td></tr>
        <tr><th>备注</th><td colspan="3"><textarea data-f="notes" rows="3"></textarea></td></tr>
      </table>
      <datalist id="raceList"></datalist>
      <datalist id="classList"></datalist>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>属性 <span class="muted">（含种族加值）</span></h2></div>
      <table class="trpg-table" id="attrTable"></table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>技能熟练 <span class="muted">（每项 +2）</span></h2></div>
      <table class="trpg-table" id="skillTable"></table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>战斗 <span class="muted">（未填时按规则自动计算）</span></h2></div>
      <table class="trpg-table">
        <tr><th>HP</th><td><input type="number" data-f="hp" min="0"></td>
            <th>AC</th><td><input type="number" data-f="ac" min="0"></td></tr>
        <tr><th>建议 HP</th><td colspan="3" id="hpHint"></td></tr>
      </table>
    </section>

    <div class="row-actions" style="justify-content:flex-end; padding:12px 0;">
      <button type="button" class="btn-sm" id="saveBtn">保存</button>
    </div>
  `;
  trpgMain.appendChild(form);

  const raceList = document.getElementById("raceList");
  for (const r of Object.keys(rules.races)) {
    const opt = document.createElement("option");
    opt.value = r;
    raceList.appendChild(opt);
  }
  const classList = document.getElementById("classList");
  for (const c of Object.keys(rules.classes)) {
    const opt = document.createElement("option");
    opt.value = c;
    classList.appendChild(opt);
  }

  form.querySelectorAll("[data-f]").forEach((el) => {
    el.value = editing[el.dataset.f] ?? "";
  });

  const attrTable = document.getElementById("attrTable");
  const skillTable = document.getElementById("skillTable");
  const hpHint = document.getElementById("hpHint");

  function refresh() {
    const data = readForm();
    const calc = computeSheet(data);
    attrTable.innerHTML = "";
    for (const attr of rules.attributes) {
      const key = attrKey(attr);
      const tr = document.createElement("tr");
      tr.innerHTML = `<th>${attr}</th>`;
      const tdScore = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.min = 1;
      input.max = 30;
      input.value = data[key] ?? 8;
      input.dataset.attr = key;
      tdScore.appendChild(input);
      tr.appendChild(tdScore);
      const tdMod = document.createElement("td");
      tdMod.className = "muted";
      const bonus = (rules.races[data.race] || {})[attr] || 0;
      tdMod.textContent = `加值 ${abilityMod(calc.scores[key]) >= 0 ? "+" : ""}${abilityMod(calc.scores[key])}${bonus ? `（种族+${bonus}）` : ""}`;
      tr.appendChild(tdMod);
      attrTable.appendChild(tr);
    }
    skillTable.innerHTML = "";
    for (const [skill, attr] of Object.entries(rules.skills)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<th>${skill}</th><td class="muted">${attr}</td>`;
      const tdProf = document.createElement("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = (data.proficient_skills || []).includes(skill);
      cb.dataset.skill = skill;
      tdProf.appendChild(cb);
      tr.appendChild(tdProf);
      const tdMod = document.createElement("td");
      const mod = calc.skillMods[skill];
      tdMod.textContent = `${mod >= 0 ? "+" : ""}${mod}`;
      tr.appendChild(tdMod);
      skillTable.appendChild(tr);
    }
    const suggestedHp = calc.hpDie + abilityMod(calc.scores.con_score);
    const suggestedAc = 10 + abilityMod(calc.scores.dex_score);
    hpHint.textContent = `职业 HP 骰 d${calc.hpDie} + 体质加值 = ${suggestedHp}；敏捷加值 AC = ${suggestedAc}（可在上方手动覆盖）`;
  }

  function readForm() {
    const data = { ...editing };
    form.querySelectorAll("[data-f]").forEach((el) => {
      const key = el.dataset.f;
      if (key === "level" || key === "hp" || key === "ac") data[key] = Number(el.value) || 0;
      else data[key] = el.value;
    });
    form.querySelectorAll("[data-attr]").forEach((el) => {
      data[el.dataset.attr] = Number(el.value) || 8;
    });
    data.proficient_skills = [...form.querySelectorAll("[data-skill]:checked")].map((el) => el.dataset.skill);
    return data;
  }

  form.addEventListener("input", refresh);
  refresh();

  document.getElementById("saveBtn").addEventListener("click", async () => {
    const data = readForm();
    if (!data.char_name.trim()) {
      showToast("请填写角色名", true);
      return;
    }
    try {
      const isNew = !editing.id;
      const url = isNew ? "/api/me/characters" : `/api/me/characters/${editing.id}`;
      const method = isNew ? "POST" : "PUT";
      const saved = await apiFetch(url, { method, body: JSON.stringify(data) });
      showToast(isNew ? `角色创建成功 (#${saved.id})` : "已保存");
      await loadList();
    } catch (err) {
      showToast(err.message, true);
    }
  });
}

async function loadList() {
  trpgMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  try {
    const data = await apiFetch("/api/me/characters");
    chars = data.characters;
    currentId = data.current_id;
    renderList();
  } catch (err) {
    trpgMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}

async function init() {
  if (!requireAuth()) return;
  try {
    rules = await apiFetch("/api/trpg/rules");
  } catch (err) {
    trpgMain.innerHTML = `<p class="loading-msg error">规则数据加载失败</p>`;
    return;
  }
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    loadList();
  });
}

init();
```

- [ ] **Step 1: 创建 `trpg.html`**（见上方完整 HTML）

- [ ] **Step 2: 创建 `trpg.js`**（见上方完整实现）

- [ ] **Step 3: `profile.css` 末尾追加编辑器样式**

```css
/* 跑团车卡编辑器 */
.trpg-table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}
.trpg-table th,
.trpg-table td {
  border: 1px solid var(--border, #ddd);
  padding: 6px 10px;
  text-align: left;
  font-size: 14px;
}
.trpg-table input[type="text"],
.trpg-table input[type="number"],
.trpg-table textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 4px 6px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
}
.trpg-editor .settings-section {
  margin-bottom: 16px;
}
```

（若 `profile.css` 没有 `--border` 变量，直接用 `#ddd`。以实际文件为准。）

- [ ] **Step 4: 手动验证**

```bash
python -m checkin_gallery 2>&1 &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/profile/trpg
kill %1
```

Expected: `200`。浏览器打开页面：登录后可看到列表；新建 → 填写 → 保存 → 列表出现；编辑/切换/删除各操作生效。

- [ ] **Step 5: Commit**

```bash
git add checkin_gallery/static/trpg.html checkin_gallery/static/trpg.js checkin_gallery/static/profile.css
git commit -m "feat(网页): 新增跑团车卡管理页与 Excel 式分区编辑器"
```

---

### Task 9: 前端角色卡查看页（`char_view.html` + `char_view.js`）

**Files:**
- Create: `checkin_gallery/static/char_view.html`
- Create: `checkin_gallery/static/char_view.js`
- Modify: `checkin_gallery/static/profile.css`（追加只读展示样式）

**Interfaces:**
- Consumes: `GET /api/characters/{user_id}/{char_id}`、`GET /api/trpg/rules`、`GalleryAuth`

**页面结构（`char_view.html`）：**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>角色卡 · 打卡图库</title>
  <link rel="stylesheet" href="/static/gallery.css" />
  <link rel="stylesheet" href="/static/profile.css" />
</head>
<body>
  <header class="toolbar profile-toolbar">
    <a href="javascript:history.back()" class="back-link">← 返回</a>
    <nav class="profile-nav">
      <a href="/profile">主页</a>
      <a href="/profile/checkin">打卡</a>
      <a href="/profile/shop">商店</a>
      <a href="/profile/alarms">闹钟</a>
      <a href="/profile/trpg">跑团</a>
      <a href="/guestbook">留言簿</a>
      <a href="/profile/settings">设置</a>
    </nav>
    <div class="auth-area" id="authArea"></div>
  </header>

  <main class="profile-main" id="charViewMain">
    <p class="loading-msg">加载中…</p>
  </main>

  <script src="/static/auth.js"></script>
  <script src="/static/char_view.js"></script>
</body>
</html>
```

**`char_view.js` 核心结构：**

```javascript
const charViewMain = document.getElementById("charViewMain");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    window.location.href = "/";
    return false;
  }
  return true;
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...GalleryAuth.headers(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    GalleryAuth.clear();
    window.location.href = "/";
    throw new Error("未登录");
  }
  if (res.status === 403) {
    throw new Error("对方未公开角色卡");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "操作失败");
  return data;
}

function abilityMod(score) {
  return Math.floor((Number(score || 8) - 10) / 2);
}

function attrKey(name) {
  return { "力量": "str_score", "敏捷": "dex_score", "体质": "con_score",
           "智力": "int_score", "感知": "wis_score", "魅力": "cha_score" }[name] || "";
}

function fmtMod(v) {
  return `${v >= 0 ? "+" : ""}${v}`;
}

function renderView(char, rules) {
  charViewMain.innerHTML = "";

  const head = document.createElement("div");
  head.className = "section-head";
  head.innerHTML = `<h2>【${escapeHtml(char.char_name)}】</h2>
    <span class="muted">${escapeHtml(char.display_name)} 的角色卡</span>`;
  charViewMain.appendChild(head);

  const meta = document.createElement("p");
  meta.className = "muted";
  meta.textContent = `Lv.${char.level} ${char.race} ${char.class_name} · HP ${char.hp} · AC ${char.ac}`;
  charViewMain.appendChild(meta);

  const attrSec = document.createElement("section");
  attrSec.className = "settings-section";
  attrSec.innerHTML = `<div class="section-head"><h2>属性</h2></div>`;
  const attrTable = document.createElement("table");
  attrTable.className = "trpg-table";
  for (const attr of rules.attributes) {
    const key = attrKey(attr);
    const score = char.scores[key] ?? 8;
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${attr}</th><td>${score}</td><td class="muted">${fmtMod(abilityMod(score))}</td>`;
    attrTable.appendChild(tr);
  }
  attrSec.appendChild(attrTable);
  charViewMain.appendChild(attrSec);

  const skillSec = document.createElement("section");
  skillSec.className = "settings-section";
  skillSec.innerHTML = `<div class="section-head"><h2>技能</h2></div>`;
  const skillTable = document.createElement("table");
  skillTable.className = "trpg-table";
  for (const [skill, attr] of Object.entries(rules.skills)) {
    const mod = char.skill_mods[skill];
    const proficient = (char.proficient_skills || []).includes(skill);
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${skill}</th><td class="muted">${attr}</td>
      <td>${proficient ? "熟练" : ""}</td><td>${mod !== undefined ? fmtMod(mod) : ""}</td>`;
    skillTable.appendChild(tr);
  }
  skillSec.appendChild(skillTable);
  charViewMain.appendChild(skillSec);

  if (char.notes) {
    const noteSec = document.createElement("section");
    noteSec.className = "settings-section";
    noteSec.innerHTML = `<div class="section-head"><h2>备注</h2></div>
      <p style="white-space:pre-wrap">${escapeHtml(char.notes)}</p>`;
    charViewMain.appendChild(noteSec);
  }
}

async function init() {
  if (!requireAuth()) return;
  const segs = window.location.pathname.split("/").filter(Boolean);
  const user_id = segs[segs.length - 2];
  const char_id = segs[segs.length - 1];
  try {
    const [char, rules] = await Promise.all([
      apiFetch(`/api/characters/${user_id}/${char_id}`),
      apiFetch("/api/trpg/rules"),
    ]);
    renderView(char, rules);
  } catch (err) {
    charViewMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}

init();
```

- [ ] **Step 1: 创建 `char_view.html`**（见上方完整 HTML）

- [ ] **Step 2: 创建 `char_view.js`**（见上方完整实现）

- [ ] **Step 3: `profile.css` 追加只读样式**（若 Task 8 已追加 `.trpg-table` 等则复用，无需重复；只需确认 `.muted` 类存在于 `profile.css`，不存在则追加 `.muted { color: #888; }`）

- [ ] **Step 4: 手动验证**

浏览器访问 `/trpg/char/<uid>/<id>`：
- 他人卡且目标 `char_public=false` → 显示"对方未公开角色卡"
- 他人卡公开 / 本人卡 → 正常渲染只读分区
- 未登录 → 跳转首页登录

- [ ] **Step 5: Commit**

```bash
git add checkin_gallery/static/char_view.html checkin_gallery/static/char_view.js checkin_gallery/static/profile.css
git commit -m "feat(网页): 新增角色卡只读查看页"
```

---

### Task 10: 设置页隐私区块（`settings.html` + `settings.js`）

**Files:**
- Modify: `checkin_gallery/static/settings.js`（`renderPage` 增加隐私区块 + 加载合并 `/api/me/settings`）
- Test: 手动

**Interfaces:**
- Consumes: `GET/PUT /api/me/settings`（Task 7）

- [ ] **Step 1: `settings.js` 增加隐私数据加载**

在 `loadSettings` 中并行请求设置数据：

```javascript
async function loadSettings() {
  if (!requireAuth()) return;
  settingsMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  try {
    const [titleData, userSettings] = await Promise.all([
      apiFetch("/api/me/titles/settings"),
      apiFetch("/api/me/settings"),
    ]);
    settingsData = titleData;
    userSettingsData = userSettings;
    renderPage();
  } catch (err) {
    settingsMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}
```

文件顶部声明 `let userSettingsData = { privacy: {} };`

- [ ] **Step 2: `renderPage` 增加隐私区块（插在称号区块之前）**

在 `renderPage()` 函数体开头追加：

```javascript
  const privacySec = document.createElement("section");
  privacySec.className = "settings-section";
  privacySec.innerHTML = `
    <div class="section-head"><h2>隐私设置</h2></div>
    <label class="privacy-row">
      <span>允许他人查看我的角色卡</span>
      <input type="checkbox" id="charPublicToggle" ${userSettingsData.privacy.char_public === false ? "" : "checked"} />
    </label>
    <p class="preview-hint">关闭后，其他用户无法在网页端查看你的角色卡（跑团车卡页）。</p>
  `;
  settingsMain.appendChild(privacySec);

  document.getElementById("charPublicToggle").addEventListener("change", async (e) => {
    try {
      userSettingsData = await apiFetch("/api/me/settings", {
        method: "PUT",
        body: JSON.stringify({ privacy: { char_public: e.target.checked } }),
      });
      showToast(e.target.checked ? "已允许他人查看角色卡" : "已隐藏角色卡");
    } catch (err) {
      e.target.checked = !e.target.checked;
      showToast(err.message, true);
    }
  });
```

- [ ] **Step 3: `profile.css` 追加开关样式**

```css
.privacy-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  font-size: 14px;
}
.privacy-row input[type="checkbox"] {
  width: 18px;
  height: 18px;
}
```

- [ ] **Step 4: 手动验证**

浏览器打开 `/profile/settings`：能看到隐私开关；切换后刷新保持；勾选状态与 `GET /api/me/settings` 一致。

- [ ] **Step 5: Commit**

```bash
git add checkin_gallery/static/settings.js checkin_gallery/static/profile.css
git commit -m "feat(网页): 设置页新增角色卡隐私开关"
```

---

### Task 11: 同步维护（菜单文案 + specs + KNOWLEDGE_BASE）

**Files:**
- Modify: `plugins/menu/bot_menu_text.py`
- Modify: `specs/plugin-catalog.md`
- Modify: `specs/database.md`（如有角色表描述则删）
- Modify: `specs/web-gallery.md`
- Modify: `KNOWLEDGE_BASE.md`

**Interfaces:**
- Consumes: 全部先前任务的最终状态

- [ ] **Step 1: 更新 `plugins/menu/bot_menu_text.py` 角色命令文案**

将原 28-34 行替换为：

```
/角色 查看 查看我的当前角色卡
/角色 切换 <编号> 切换当前角色
/角色 列表 列出我的角色
/角色 删除 <编号> 删除角色
/角色 创建/编辑 网页端车卡：/profile/trpg
```

- [ ] **Step 2: 更新 `specs/plugin-catalog.md` 的 `trpg_char` 行**

原第 30 行（`/角色 创建/查看/编辑/切换/列表/删除` / 分步创建）更新为：

```
| `trpg_char/` | `TrpgCharPlugin` | `trpg_char` | CommandPlugin | `/角色 查看/列表/切换/删除` | DND5E 角色卡：查看(仅自己)/列表/切换/删除；创建与编辑迁移至网页端 `/profile/trpg` |
```

- [ ] **Step 3: 更新 `specs/database.md`**

读文件确认是否有 `dnd_characters` / `dnd_current_character` 表描述；若有则整段删除。若无则跳过此步（记到 commit message 里说明）。

- [ ] **Step 4: 更新 `specs/web-gallery.md`**

追加"跑团车卡"章节（描述新端点、页面路由、隐私开关、JSON 文件存储位置与 `BOTERO_TRPG_CHARS_ROOT`/`BOTERO_USER_SETTINGS_ROOT` env 变量）。

- [ ] **Step 5: 更新 `KNOWLEDGE_BASE.md`**

- 角色卡存储：SQLite `dnd_characters` 表 → `server_data/trpg_chars/<user_id>/` JSON 文件（meta.json + <char_id>.json）
- 插件目录：`trpg_char` 描述更新；`core/character_store.py`、`core/user_settings.py`、`core/trpg/` 新模块记录
- 网页端：新端点与页面清单
- 个人设置：`server_data/user_settings/<user_id>.json`，`privacy.char_public` 键约定

- [ ] **Step 6: 全量回归**

```bash
python test/test_character_store.py
python test/test_user_settings.py
python test/test_trpg.py
python test/test_trpg_char.py
python test/test_trpg_session.py
python test/test_dice.py
```

Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/menu/bot_menu_text.py specs/ KNOWLEDGE_BASE.md
git commit -m "docs(跑团): 同步菜单文案、specs 与知识库至 JSON 存储与网页车卡"
```

---

### Task 12: 端到端手测清单

**Files:** 无

- [ ] **Step 1: 启动 bot 与 web**

```bash
python main.py &          # bot
python -m checkin_gallery &  # web
```

- [ ] **Step 2: QQ 端验证**

- `/角色 查看` → 显示当前角色卡（无角色时引导到网页端）
- `/角色 查看 @他人` → 仍显示**自己的**角色卡（忽略 @）
- `/角色 创建` → 回复引导到 `/profile/trpg`
- `/角色 列表` / `/角色 切换 1` / `/角色 删除 1` → 正常
- `.r 力量`、`.rc 侦查`、`.r 侦查+10` → 引用角色属性正常

- [ ] **Step 3: 网页端验证**

- 登录 → 顶部导航出现「跑团」→ 进入 `/profile/trpg`
- 新建角色：填姓名/种族/职业，属性改动时加值实时变化，技能勾选时加值 +2，HP/AC 提示实时更新 → 保存
- 刷新页面 → 角色在列表，可编辑/设为当前/删除（删除有确认框）
- 打开 `/trpg/char/<uid>/<id>` → 只读渲染正确
- 设置页关闭"允许他人查看我的角色卡" → 用另一账号访问该卡 URL → 显示"对方未公开角色卡"
- 设置页重新打开开关 → 另一账号可正常查看

- [ ] **Step 4: 数据文件检查**

```bash
ls server_data/trpg_chars/ server_data/user_settings/
```

Expected: 每个用过的用户有目录；meta.json 内容正确（current_id/order）；无 `.tmp` 残留

- [ ] **Step 5: 收尾 commit（如手测发现问题则新建修复 commit）**

```bash
git status
```
