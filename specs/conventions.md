# Spec: 编码约定与隐式知识

> 关联规范: [plugins.md](plugins.md) | [database.md](database.md) | [architecture.md](architecture.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-08-22

本文档记录项目中**不在代码中显式声明**但必须遵守的约定和隐式知识。新开发者（含 AI）最容易在这里犯错。

---

## Constraint: Commit 提交分块

**每条 commit 只承载一个逻辑变更**，禁止把互不相关的改动揉进同一个 commit。

**MUST:**
- 一个 commit = 一个可独立描述的逻辑单元（`feat` / `fix` / `test` / `docs` / `refactor` / `chore` 等），按类型与关注点拆分
- 同一逻辑变更的**配套文件必须在同一个 commit 内**：代码 + 对应行为测试 + 关联 spec + `BOT_MENU_TEXT` + `CHANGELOG.md` + `KNOWLEDGE_BASE.md`（配合 `specs/README.md` 的同步维护表）
- 独立事项（预先存在的测试修复、依赖升级、格式化、无关文档）与功能开发**分 commit 提交**

**MUST NOT:**
- 把多个无关改动合并为一个 commit（如"功能 + 无关测试修复 + 文档"一把梭）
- 让一个 commit 承载两种以上语义类型（如 `feat` 夹带无关 `fix` / `test`）

**分块判断示例:**
- 功能改动 + 其行为测试 + spec 描述 + CHANGELOG/版本 bump → 同一 `feat`/`fix` commit
- 预先存在的测试日期过期修复 → 独立 `test` commit（不 bump 版本）
- 纯文档/内部重构 → 独立 `docs`/`refactor` commit（可只记 CHANGELOG 不 bump）

**辅助:** `.githooks/commit-msg` 钩子在暂存文件过多（>12 个）时输出分块提示（警告不阻断，人工判断）。

---

## Constraint: 菜单文本集中管理

`plugins/menu/bot_menu_text.py` 的 `BOT_MENU_TEXT` 是指令文本的**唯一来源**。

```python
from plugins.menu.bot_menu_text import BOT_MENU_TEXT
```

- `MenuPlugin`（响应 `/菜单`）读取 `BOT_MENU_TEXT`
- LLM 子系统也读取 `BOT_MENU_TEXT` 获取指令列表
- **任何新增/修改指令时，必须在同一 commit 中更新 `BOT_MENU_TEXT`**

**MUST NOT:** 在其他插件、文档或提示词中硬编码指令说明文本。

---

## Constraint: 打卡周边界（08:00 偏移）

打卡周的定义是 **周一 08:00 到次周一 08:00**，不是自然周的 00:00 边界。

```python
from core.utils import get_monday_to_monday

start, end = get_monday_to_monday()
# start = "2026-06-29 08:00:00" (当前周的周一 08:00)
# end   = "2026-07-06 08:00:00" (下周一的 08:00)
```

实现细节（`core/utils.py:13-21`）：
```python
def get_monday_to_monday(date=None):
    if date is None:
        date = datetime.today()
    date = date - timedelta(hours=8)  # 向前偏移 8 小时
    weekday = date.weekday()
    start = date - timedelta(days=weekday)
    end = start + timedelta(days=7)
    return start.strftime("%Y-%m-%d 08:00:00"), end.strftime("%Y-%m-%d 08:00:00")
```

**同样使用 08:00 偏移的地方:**
- `utils.day_of_year()` — 热度图日期索引
- `database_manager.get_user_streaks()` — 连续打卡天数计算
- `webapp/gallery/dates.py` — Web 端结算日逻辑

**MUST:** 任何新增的"周"相关功能必须使用此偏移，否则跨周边界会出现不一致。

---

## Constraint: 超级用户与权限

```python
# 在 core/base.py 中定义:
SUPER_USER = [1057613133]    # 主人的 QQ 号
BOT_QQ = "3915014383"       # 机器人自己的 QQ 号
NICKNAME = "小埃同学"        # 机器人昵称
```

**权限等级:**
- `self.super_user()` — `user_id in SUPER_USER`
- `self.admin_user()` — super_user **或** 群内角色为 `"admin"` / `"owner"`

**使用模式:**
```python
def match(self, event_type):
    return (self.on_full_match("/系统状态")
            and self.super_user())       # 仅主人可用

def match(self, event_type):
    return (self.on_full_match("/发金币")
            and self.admin_user())       # 主人或群管理可用
```

---

## Constraint: 路径约定

项目存在两套并行路径指向同一数据：

| 常量 | 值 | 用途 |
|------|-----|------|
| `context.python_data_path` | `"./server_data"` | Python 文件 I/O |
| `context.llonebot_data_path` | `"/app/llonebot/server_data"` | OneBot API 调用中使用 |
| `context.onebot_qq_volume` | `"/var/lib/docker/volumes/onebot_qq_volume/_data"` | Docker 卷路径 |

目录结构：
```
server_data/
  record_images/<user_id>/   ← 打卡图片缓存（按用户分目录）
  personal_records/          ← 生成的个人档案图片
  thumb_cache/               ← Web 端缩略图缓存
```

**MUST:**
- Python 脚本文件 I/O 使用 `python_data_path`
- 传递给 OneBot API 的路径参数使用 `llonebot_data_path`
- Web 应用可通过 `BOTERO_IMAGE_ROOT` 环境变量覆盖

---

## Constraint: 日志

```python
from core.logger import logger

logger.info("正常信息")
logger.error("错误信息")
logger.exception("异常（自动附带 traceback）")
```

- 日志格式: `[bot] %(asctime)s - %(levelname)s - %(message)s`
- 日志级别: `INFO`
- **MUST NOT** 使用 `print()` 代替 logger
- `main.py` 的 `plugin_pool()` 已在框架层统一 catch 插件异常并记录 `logger.exception()`；插件 `handle()` 不再强制自行 try/except（但复杂子逻辑仍建议有自己的错误处理）

---

## Constraint: 导入约定

```python
# 插件中导入 core 模块 — 使用绝对路径
from core.cq import text, image, at, reply
from core.utils import register_plugin, get_monday_to_monday
from core.base import Plugin, CommandPlugin, TimedHeartbeatPlugin
from core.event import Event

# 从插件导入纯数据 — 允许（如 title.py 的标题定义）
from plugins.title import get_title_def, TITLE_DEFS
from plugins.menu.bot_menu_text import BOT_MENU_TEXT

# 类型导入 — 使用 TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.base import Plugin
```

**MUST NOT:**
- 使用相对导入（`from . import ...` / `from .. import ...`）
- 从 `plugins` 导入另一个插件的类实例（导入纯函数/数据是可以的）
- 跨包做循环导入（如 `plugins` ↔ `webapp` 之间不要互相导入）

---

## Constraint: 错误处理模式

```python
def handle(self):
    try:
        # 业务逻辑
        result = self._do_something()
        if not result:
            self.api.send_msg(text("操作失败，请稍后再试喵~"))
            return
        self.api.send_msg(text("操作成功喵~"))
    except Exception as e:
        logger.exception(f"插件 {self.name} 处理异常")
        self.api.send_msg(text("出了点问题，请稍后再试喵~"))
```

**MUST:**
- 异常由 `main.py` 框架层统一记录 `logger.exception()`，不会静默死线程
- 插件 `handle()` 内可以不做最外层 try/except（框架已保护），但复杂子逻辑仍建议有自己的错误处理
- 给用户返回友好的错误消息（使用 bot 的语气：喵~、波浪线）

**ApiWrapper 错误返回值:**
- `call_api` 超时 → 返回 `{"status": "failed"}`
- API 调用失败 → `ret.get("status") != "ok"`
- 大多数方法对失败返回 `0` / `""` / `False`
- 使用前检查返回值

---

## Constraint: 添加依赖

项目**没有** `pyproject.toml` / `setup.py`；根目录 `requirements.txt` 是 bot 全量依赖清单（`pip install -r requirements.txt`），`webapp/requirements.txt` 是 webapp 子集。

当前依赖：
- **机器人核心:** `websocket-client`, `requests`, `Pillow`, `tzdata`（仅 Windows——系统无 IANA 时区库，`plugins/\immortal_lottery` 的 `ZoneInfo` 依赖）
- **周报热词:** `jieba`
- **LLM（已弃用）:** `openai`
- **更新:** `GitPython`
- **系统监控:** `psutil`（可选，MonitorPlugin 会自动降级）
- **测试:** `pytest`（统一回归入口，隔离与布局见 `test/conftest.py` 头注释）
- **Web 应用:** `fastapi`, `uvicorn`, `python-multipart` 等（见 `webapp/requirements.txt`）

**添加新依赖的流程:**
1. 在根 `requirements.txt` 添加（webapp 专用依赖同步进 `webapp/requirements.txt`）
2. 在本文件中记录
3. 考虑做可选依赖（如同 `psutil` 的处理方式）

---

## Constraint: 消息风格

bot 的回复风格（由 `core/llm/prompts/chat_prompt.md` 定义）：
- 使用波浪线（~）代替句号
- 偶尔使用"喵~"结尾
- 使用颜文字（如 `(╹ڡ╹ )`、`(｡･ω･｡)`）
- 自称"小埃"

插件 `handle()` 中发送错误消息时应保持此风格。

---

## Constraint: 硬编码常量

以下值**已硬编码在源码中**，修改时需注意：

| 常量 | 位置 | 值 |
|------|------|-----|
| WebSocket URL | `main.py` | `ws://127.0.0.1:3001` |
| WS Token | `main.py` | `123456` |
| 默认群号 | `core/context.py` | `296470819` |
| 超级用户 | `core/base.py` | `[1057613133]` |
| 机器人 QQ | `core/base.py` | `"3915014383"` |
| 下载代理 | `core/utils.py` | `127.0.0.1:7890` |

以上六个值仍硬编码在源码，修改需直接编辑（精确 file:line 见 `kb/QUICK_REFERENCE.md` 硬编码常量表）。路径/盐/端口/开关类配置已环境变量化：约 30 个 `BOTERO_*` 变量集中读入 `core/config.py`，部署侧单一来源 `scripts/botero.env`。

---

## 常见 AI 错误预防清单

以下错误在新功能开发中最常见，AI 辅助编程时务必检查：

- [ ] 1. 新增插件 → 是否加了 `@register_plugin`？是否选了正确的基类（`Plugin` / `CommandPlugin` / `TimedHeartbeatPlugin`）？
- [ ] 2. 新增指令 → 是否更新了 `BOT_MENU_TEXT`？
- [ ] 3. 插件异常 → 框架层统一捕获，不需要每个 handle() 自行 try/except
- [ ] 4. 修改数据库 → 是否用了参数化查询（`?` 占位符）？
- [ ] 5. 新增表/列 → 是否用了 `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN`？
- [ ] 6. 涉及"周"的逻辑 → 是否用了 08:00 偏移？
- [ ] 7. 使用 `self.bot_event.group_id` → 是否检查了 `None`？
- [ ] 8. 使用 `self.args` → 是否在 `match()` 中调用了 `on_command`/`on_command_any`，或继承 `CommandPlugin`？
- [ ] 9. 插件类 → `name` 和 `description` 是否非空？
- [ ] 10. 是否有 `import` 引入了新依赖？→ 是否记录？
- [ ] 11. 是否用了 `async`/`await`？→ 系统不支持
- [ ] 12. 是否用了 f-string 拼接 SQL？→ 改用 `?` 参数化
- [ ] 13. 是否在 `match()` 中有副作用（发消息/写库）？→ 移到 `handle()`
- [ ] 14. 是否修改了 `core/` 模块？→ 确认是否有必要，更新对应 spec
- [ ] 15. 是否跨插件导入了业务逻辑类？→ 改用共享数据模块或数据库
- [ ] 16. 是否把无关改动揉进了一个 commit？→ 按逻辑分块（功能/修复/测试/文档），配套文件同 commit
