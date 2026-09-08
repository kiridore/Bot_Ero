# T0.1 配置分侧与 edition 引入 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `config.yaml` 引入 `bot.edition: private|community`（缺省 private），必填键按部署形态拆分——社区形态（纯 bot）不要求 `bot.default_group`/`onebot`/`timeline` 配置，并导出后续任务（T0.2-T0.4、T1.2、T1.5）消费的形态常量。

**Architecture:** 只改 `core/config.py`（双形态接缝白名单的合法接缝之一，见 `specs/conventions.md` §双形态接缝）：`_load()` 内按 raw 配置中的 edition 决定校验哪组必填键；模块级常量区新增 `EDITION`/`SYSTEM_PLUGINS_CONF`/`COMMUNITY_*` 并把 `DEFAULT_GROUP_ID`、`timeline.*`、`onebot.*` 的读取改为宽松（缺省 None/空串）。私有部署行为零变化。

**Tech Stack:** Python 3 + PyYAML（现有依赖），unittest 风格 pytest 用例（`test/test_config_loader.py` 既有模式：`BOTERO_CONFIG` + `importlib.reload`）。

**Spec:** `docs/superpowers/specs/2026-09-08-config-edition-split-design.md`（本计划的依据，执行者必读）；任务来源 `docs/community/development-plan.md` §T0.1；决策背景 `docs/community/community-edition-plan.md` D5/D8/D11。

## Global Constraints

- **一个逻辑变更一个 commit**（`specs/conventions.md` §Commit 提交分块，仓库规则优先于技能默认的逐任务提交）：本计划 Task 1-3 累积变更，Task 4 统一提交，commit 消息中文 Conventional Commits：`feat(配置): bot.edition 部署形态与必填键分侧`。
- **edition 差异只允许在 5 处接缝**（`specs/conventions.md` §双形态接缝）；本任务全部落在 `core/config.py` 接缝内，**不得**在其他文件添加 edition 判断。
- **私有形态零行为变化**：现有全部 pytest 用例（含 `test_config_loader.py` 既有 `REQUIRED_MINIMAL` 断言）必须原样通过。
- 内部基础设施变更：CHANGELOG 记 `[未发布]` 节、**不 bump** `BOTERO_VERSION`（AGENTS.md §CHANGELOG 约定）。
- 测试不得触碰真实 `server_data`/`data.db`；本任务用例仅写临时目录 config 文件并 reload 模块（既有模式，无需 `write_config`）。
- `DEFAULT_GROUP_ID=None` 的**发送兜底适配属 T0.2**、时间线上报 no-op 属 T0.3——本任务只做配置层，不改 `core/api.py`/`core/timeline_client.py`。

---

### Task 1: 必填分侧与 edition 校验

**Files:**
- Modify: `core/config.py:24-44`（`_REQUIRED` 元组与 `_load()`）
- Test: `test/test_config_loader.py`（`TestLoad` 类追加用例 + 顶部新模板常量）

**Interfaces:**
- Consumes: 现有 `_load(path) -> dict`、`sys.exit` 报错模式（错误消息含缺失键点路径）。
- Produces: `_load` 接受社区最小配置（缺 `bot.default_group`、整段 `onebot`/`timeline`）；非法 `bot.edition` 值启动即退出。后续任务依赖此行为，无新函数签名。

- [ ] **Step 1: Write the failing tests**

在 `test/test_config_loader.py` 顶部 `REQUIRED_MINIMAL` 之后新增模板常量：

```python
# 社区形态最小配置：无 default_group / onebot / timeline 节
COMMUNITY_MINIMAL = """
bot:
  edition: community
  qq: "123456"
  nickname: 测试bot
  super_users: [1, 2]
  ws_url: ws://127.0.0.1:3001
  ws_token: "123456"
  llonebot_data_path: /tmp/onebot_data
  python_data_path: ./server_data
auth:
  salt: test-salt
"""
```

`TestLoad` 类内追加三个用例：

```python
    def test_community_minimal_loads_without_web_side_keys(self):
        """社区形态：缺 default_group / onebot / timeline 不退出。"""
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            data = _load(Path(_write(tmp, COMMUNITY_MINIMAL)))
            self.assertEqual(data["bot"]["edition"], "community")

    def test_private_missing_default_group_exits(self):
        """私有形态（缺省 edition）：default_group 仍必填。"""
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            del bad["bot"]["default_group"]
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _load(p)
            self.assertIn("bot.default_group", str(ctx.exception))

    def test_invalid_edition_exits(self):
        """非法 edition 值启动即退出并提示可选值。"""
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            bad["bot"]["edition"] = "saas"
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _load(p)
            self.assertIn("bot.edition", str(ctx.exception))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test/test_config_loader.py -v`
Expected: 新增 3 例 FAIL——前两例 `SystemExit` 未抛出（现有 `_REQUIRED` 不含按形态拆分），第三例同理（`_load` 不校验 edition）。

- [ ] **Step 3: Implement the split in `_load`**

`core/config.py` 中，把现有 `_REQUIRED` 元组（第 24-34 行附近）整体替换为：

```python
_EDITIONS = ("private", "community")

# 必填键（点路径），按部署形态拆分：
# - 两种形态共有的 bot 基础项 + auth.salt
# - 私有形态额外要求：默认群（单群假设兜底）、OneBot HTTP（webapp 昵称解析）、
#   时间线上报（webapp Event Server 地址）
_REQUIRED_BOT = (
    "bot.qq", "bot.nickname", "bot.super_users",
    "bot.ws_url", "bot.ws_token", "bot.llonebot_data_path", "bot.python_data_path",
    "auth.salt",
)
_REQUIRED_PRIVATE_EXTRA = (
    "bot.default_group",
    "onebot.http_url", "onebot.token",
    "timeline.url", "timeline.token",
)
```

`_load()` 中，`data = yaml.safe_load(...)` 之后、必填校验循环之前插入 edition 解析，并把循环遍历对象从 `_REQUIRED` 改为 `required`：

```python
    edition = str((data.get("bot") or {}).get("edition") or "private")
    if edition not in _EDITIONS:
        sys.exit(f"配置文件 {path} 的 bot.edition 非法：{edition}（可选 {'/'.join(_EDITIONS)}）")
    required = _REQUIRED_BOT + (_REQUIRED_PRIVATE_EXTRA if edition == "private" else ())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test/test_config_loader.py -v`
Expected: 全部 PASS（含既有用例——`REQUIRED_MINIMAL` 无 edition 键 → 走 private 分支，行为不变）。

- [ ] **Step 5: Run the full suite（本任务不提交）**

Run: `python -m pytest`
Expected: 全绿（config 模块被 conftest 以完整私有配置加载，不受影响）。

---

### Task 2: 形态常量导出与宽松读取

**Files:**
- Modify: `core/config.py:70-90`（`DEFAULT_GROUP_ID` 区）、`core/config.py:84-90`（`ONEBOT_*` 区）、`core/config.py:110` 附近（`TIMELINE_*` 区）
- Test: `test/test_config_loader.py`（`TestConstants` 类追加用例）

**Interfaces:**
- Consumes: Task 1 的 `_load`（社区最小配置可过校验后模块级代码才会执行）。
- Produces（后续任务依赖的精确签名，均模块级常量）:
  - `EDITION: str`（`"private"` | `"community"`，缺省 `"private"`）——T0.4/T0.7/T1.2/T1.6 消费
  - `SYSTEM_PLUGINS_CONF: list[str]`（缺省 `[]`）——T0.4 消费
  - `COMMUNITY_MAX_GROUPS: int`（缺省 `50`）——T1.4 消费
  - `COMMUNITY_CMD_COOLDOWN_SECONDS: int`（缺省按形态：community=3，private=0 即关闭）——T1.5 消费
  - `DEFAULT_GROUP_ID: int | None`（社区形态缺省 `None`）；`GROUP_ID` 别名跟随——T0.2 消费
  - `TIMELINE_URL: str`（缺省 `""` = 上报关闭）、`TIMELINE_TOKEN: str`——T0.3 消费

- [ ] **Step 1: Write the failing tests**

`TestConstants` 类内追加两个用例（复用既有 `_reload_with` 模式，`finally` 里恢复 conftest 配置）：

```python
    def test_community_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._reload_with(_write(tmp, COMMUNITY_MINIMAL))
            try:
                self.assertEqual(cfg.EDITION, "community")
                self.assertIsNone(cfg.DEFAULT_GROUP_ID)      # 社区形态无默认群
                self.assertIsNone(cfg.GROUP_ID)              # 旧名别名跟随
                self.assertEqual(cfg.TIMELINE_URL, "")       # 空 = 上报关闭（T0.3 消费）
                self.assertEqual(cfg.TIMELINE_TOKEN, "")
                self.assertEqual(cfg.ONEBOT_HTTP_URL, "")
                self.assertEqual(cfg.SYSTEM_PLUGINS_CONF, [])
                self.assertEqual(cfg.COMMUNITY_MAX_GROUPS, 50)
                self.assertEqual(cfg.COMMUNITY_CMD_COOLDOWN_SECONDS, 3)
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)

    def test_edition_default_private_and_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = yaml.safe_load(REQUIRED_MINIMAL)
            raw["bot"]["system_plugins"] = ["menu", "register"]
            raw["community"] = {"max_groups": 5, "cmd_cooldown_seconds": 10}
            cfg = self._reload_with(_write(tmp, yaml.safe_dump(raw, allow_unicode=True)))
            try:
                self.assertEqual(cfg.EDITION, "private")     # 无 edition 键 → 缺省 private
                self.assertEqual(cfg.DEFAULT_GROUP_ID, 42)
                self.assertEqual(cfg.SYSTEM_PLUGINS_CONF, ["menu", "register"])
                self.assertEqual(cfg.COMMUNITY_MAX_GROUPS, 5)
                self.assertEqual(cfg.COMMUNITY_CMD_COOLDOWN_SECONDS, 10)  # 显式覆盖不分形态
                self.assertEqual(cfg.COMMUNITY_CMD_COOLDOWN_SECONDS if False else cfg.COMMUNITY_CMD_COOLDOWN_SECONDS, 10)
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)
```

注：第二例倒数第二行断言为冗余占位笔误，实现时**删除该行**，仅保留前一行 `assertEqual(..., 10)`。

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test/test_config_loader.py::TestConstants -v`
Expected: 两例 FAIL——`cfg.EDITION` 等属性不存在（AttributeError）；`DEFAULT_GROUP_ID` 对社区配置会因 `int(_bot["default_group"])` 直接 KeyError。

- [ ] **Step 3: Implement constants**

`core/config.py` 中，`SUPER_USER = ...` 行与 `DEFAULT_GROUP_ID = int(_bot["default_group"])` 行之间插入形态常量块，并替换 `DEFAULT_GROUP_ID`/`GROUP_ID` 两行：

```python
# —— 部署形态（private=私有全功能；community=社区公共服务，纯 bot）——
EDITION = str(_bot.get("edition") or "private")
SYSTEM_PLUGINS_CONF = [str(s) for s in (_bot.get("system_plugins") or [])]  # T0.4 消费（缺省空 = 用内置集合）
_community = _sec("community")
COMMUNITY_MAX_GROUPS = int(_community.get("max_groups") or 50)
# 频控冷却秒数：显式配置不分形态生效；缺省 community=3 / private=0（关闭）
_cooldown_raw = _community.get("cmd_cooldown_seconds")
COMMUNITY_CMD_COOLDOWN_SECONDS = int(_cooldown_raw) if _cooldown_raw is not None else (3 if EDITION == "community" else 0)

_default_group = _bot.get("default_group")
DEFAULT_GROUP_ID = int(_default_group) if _default_group else None  # 社区形态可无默认群（发送兜底见 T0.2）
GROUP_ID = DEFAULT_GROUP_ID  # webapp 侧旧名，两名一键（community 形态可为 None）
```

同文件 OneBot 区与时间线区改为宽松读取（缺节/缺键 → 空串，不 KeyError）：

```python
ONEBOT_HTTP_URL = str(_onebot.get("http_url") or "")
ONEBOT_TOKEN = str(_onebot.get("token") or "")
```

```python
TIMELINE_URL = str(_timeline.get("url") or "").rstrip("/")  # 空 = 上报关闭（T0.3 消费）
TIMELINE_TOKEN = str(_timeline.get("token") or "")
```

（删除原 `GROUP_ID = DEFAULT_GROUP_ID  # webapp 侧旧名，两名一键` 行，已并入上方新块。）

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test/test_config_loader.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest`
Expected: 全绿。重点关注 webapp/周报相关用例（私有配置下 `GROUP_ID` 仍为 int，不受影响）。

---

### Task 3: 配置模板与知识库标注

**Files:**
- Modify: `config.example.yaml`（bot 节头两行 + `default_group`/`onebot`/`timeline` 注释 + 文件尾新增 `community` 节）
- Modify: `kb/QUICK_REFERENCE.md:14-39`（配置键表）

**Interfaces:**
- Consumes: Task 1-2 的键名与缺省值（模板与键表必须与实现一致）。
- Produces: 无代码接口；`config.example.community.yaml` 完整模板属 T1.7，本任务只做主模板标注。

- [ ] **Step 1: Update `config.example.yaml`**

bot 节首行前插入 edition 键、`onebot_qq_volume` 行后插入 system_plugins 键：

```yaml
bot:
  edition: private              # 部署形态：private=私有全功能 | community=社区公共服务（纯 bot，见 docs/community/）
```

```yaml
  onebot_qq_volume: ""      # docker 卷路径（裸机部署留空）
  system_plugins: []        # 可选：系统插件白名单（缺省 = menu/group_manager/startup_changelog/backup/update/auto_friend/welcome/message_logger）
```

三处既有注释改为分形态说明（保持键值不动）：

```yaml
  default_group: 296470819    # 默认群号（私有形态必填；社区形态可省 = 无默认群，无群上下文的群发将被丢弃——见 api.py 兜底）
```

```yaml
# OneBot HTTP（拉取 QQ 昵称；私有形态必填——webapp 昵称解析用；社区形态可省）
onebot:
```

```yaml
# 社区时间线上报（私有形态必填——webapp Event Server 地址；社区形态留空/省略 = 上报关闭）
timeline:
```

文件末尾（`panel` 节之后）追加：

```yaml
community:                 # 仅 edition: community 生效（见 docs/community/community-edition-plan.md）
  max_groups: 50               # 最大激活群数（入群审核超限直接拒绝）
  cmd_cooldown_seconds: 3      # 同用户同指令冷却秒数（0=关闭；私有形态缺省 0）
```

- [ ] **Step 2: Update `kb/QUICK_REFERENCE.md` 配置键表**

`bot` 节块内补两行、改一行（置于 `qq` 行之前/之后按现有顺序）：

```markdown
| `bot` | `edition` | ❌ | 部署形态 `private`（缺省）/`community`；差异约束见 `specs/conventions.md` §双形态接缝 |
| | `system_plugins` | ❌ | 系统插件白名单（缺省 = 内置 8 件套）；社区形态裁掉 message_logger/startup_changelog 等 |
```

`default_group` 行"必填"列改为 `私有✅`，说明加"社区形态可省（None）"；`onebot` 与 `timeline` 行必填列同样改为 `私有✅`，说明注明社区形态可省/留空=关闭。表后新增一行：

```markdown
| `community` | `max_groups` / `cmd_cooldown_seconds` | ❌ | 仅 community 形态生效；缺省 `50` / `3`（private 缺省 `0`=关闭频控） |
```

同时把该节首段"文件不存在或必填项缺失 → 启动即退出"补一句："必填集按 `bot.edition` 分侧（community 仅 bot 基础项 + `auth.salt`）"。

- [ ] **Step 3: Verify docs render correctly**

Run: `python -c "import yaml; yaml.safe_load(open('config.example.yaml', encoding='utf-8'))" && echo OK`
Expected: `OK`（模板 YAML 语法有效）。

---

### Task 4: CHANGELOG、全量回归与统一提交

**Files:**
- Modify: `CHANGELOG.md`（`[未发布]` 节）

**Interfaces:**
- Consumes: Task 1-3 的全部产出。
- Produces: 单一 commit，含本计划全部文件。

- [ ] **Step 1: Add CHANGELOG entry**

`CHANGELOG.md` 的 `## [未发布]` 节顶部追加（不 bump 版本——内部基础设施，私有部署零行为变化）：

```markdown
- **配置分侧与部署形态**：`config.yaml` 新增可选 `bot.edition: private|community`（缺省 private，私有部署零变化）；必填键按形态拆分——community 仅校验 bot 基础项 + `auth.salt`，不再要求 `bot.default_group`/`onebot`/`timeline`；新增 `bot.system_plugins` 与 `community` 节（`max_groups`/`cmd_cooldown_seconds`，缺省 50/3）；`DEFAULT_GROUP_ID` 社区形态可为 `None`（发送兜底与上报 no-op 由后续任务落地）。社区版任务 T0.1，计划见 `docs/superpowers/plans/2026-09-08-config-edition-split.md`
```

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest`
Expected: 全绿（含 conftest 生成的临时私有配置路径——形态缺省 private，全链路不受影响）。

- [ ] **Step 3: Commit（本计划唯一 commit，一个逻辑变更）**

```bash
git add core/config.py test/test_config_loader.py config.example.yaml kb/QUICK_REFERENCE.md CHANGELOG.md
git commit -m "feat(配置): bot.edition 部署形态与必填键分侧"
```

---

## Self-Review 结论

- **Spec 覆盖**：development-plan §T0.1 的 4 个步骤→Task 1（步骤1）、Task 2（步骤2+3）、Task 3（步骤4）、验收三条件→Task 1 Step 4/Task 2 Step 5/Task 4 Step 2 全覆盖；`DEFAULT_GROUP_ID=None` 消费方（T0.2/T0.3）已在 Global Constraints 声明边界。
- **占位符扫描**：Task 2 Step 1 测试代码中一行冗余断言已显式标注"实现时删除"，其余无 TBD/待补。
- **类型一致性**：`EDITION: str`、`SYSTEM_PLUGINS_CONF: list[str]`、`COMMUNITY_MAX_GROUPS: int`、`COMMUNITY_CMD_COOLDOWN_SECONDS: int`（缺省 community 3/private 0）、`DEFAULT_GROUP_ID: int|None` 与 Interfaces 块及 T0.2-T1.5 消费声明一致；测试断言值与实现缺省值逐一对账（50/3/None/""）。
