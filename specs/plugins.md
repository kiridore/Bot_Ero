# Spec: 插件开发契约

> 关联规范: [conventions.md](conventions.md) | [plugin-catalog.md](plugin-catalog.md) | [onebot-protocol.md](onebot-protocol.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-06-29

---

## Constraint: 插件类契约

每个插件必须满足以下最小契约，否则框架不会识别或行为未定义：

```python
from core.base import Plugin
from core.cq import text
from core.utils import register_plugin

@register_plugin                          # REQUIRED: 注册到 plugin_registry
class MyPlugin(Plugin):                   # REQUIRED: 必须继承 Plugin
    name = "my_plugin"                    # REQUIRED: 唯一标识符，用于 LLM ToolSpec
    description = "这个插件做什么。"        # REQUIRED: 用于 LLM ToolSpec 和文档

    def match(self, event_type) -> bool:  # REQUIRED: 返回 True 才执行 handle()
        return self.on_full_match("/指令")

    def handle(self):                     # REQUIRED: 执行业务逻辑
        self.api.send_msg(text("回复内容"))
```

**MUST:**
- `name` 和 `description` 必须设置，不可为空字符串
- `name` 必须在所有插件中唯一
- `@register_plugin` 必须在类定义上方
- 类必须直接或间接继承 `Plugin`

**CAN:**
- 继承 `CommandPlugin` 代替 `Plugin` 以获得自动指令解析
- 继承 `TimedHeartbeatPlugin` 代替 `Plugin` 以获得定时触发能力

---

## Constraint: 插件生命周期

每个事件到达时，框架执行以下流程：

```
OneBot 事件 → main.py on_message()
  ├── 解析 event_type: "meta" | "notice" | "message"
  └── 对 plugin_registry 中的每个 Plugin 类:
       ├── 创建新线程
       │    ├── plugin = PluginClass(raw_context)   # 新实例
       │    ├── if plugin.match(event_type):         # 匹配判断
       │    │       plugin.handle()                  # 业务处理
       │    └── 线程结束，实例被 GC
       └── 所有插件并行执行（无顺序保证）
```

**MUST NOT:**
1. **不要** 在 `__init__` 中执行重操作（每次事件都新建实例）
2. **不要** 在 `match()` 中调用 `send_msg` 或修改数据库
3. **不要** 在 `handle()` 中假设其他插件的执行顺序
4. **不要** 跨 `handle()` 调用保存实例状态（每次事件都是新实例）
5. **不要** 在插件中覆盖 `__init__` 而不调用 `super().__init__(raw_context)`

**如果需要持久状态** → 使用 `self.dbmanager` 写入数据库，或使用模块级变量。

---

## Constraint: 可用实例属性

在 `__init__` 完成后，每个插件实例拥有以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.bot_event` | `Event` | 解析后的事件数据包装器 |
| `self.api` | `ApiWrapper` | OneBot API 客户端，用于发消息和调用 API |
| `self.dbmanager` | `DbManager` | 数据库访问层，每次创建新的 sqlite3 连接 |

### `self.bot_event` (Event) 属性

```python
# 在 match() 或 handle() 中访问:
self.bot_event.user_id      # int | None   — 发送者 QQ 号
self.bot_event.group_id     # int | None   — 群号（私聊时为 None）
self.bot_event.message      # list[dict]   — 消息段列表
self.bot_event.message_id   # int | None   — 消息 ID
self.bot_event.post_type    # str | None   — "message" | "notice" | "meta_event" | ...
self.bot_event.notice_type  # str | None   — 通知子类型
self.bot_event.request_type # str | None   — 请求子类型（如 "friend"）
self.bot_event.sender       # dict | None  — 发送者信息
self.bot_event.time         # int | None   — 事件时间戳
self.bot_event.is_group     # bool         — message_type == "group"
self.bot_event.is_private   # bool         — message_type == "private"
self.bot_event.raw          # dict         — 原始 OneBot 事件 JSON
```

### `self.api` (ApiWrapper) 关键方法

```python
# 发送消息（详见 onebot-protocol.md）
self.api.send_msg(segment1, segment2, ...)    # 自动判断群聊/私聊
self.api.send_group_msg(*segments)            # 强制发群聊
self.api.send_private_msg(*segments)          # 强制发私聊
self.api.send_forward_msg([segment_list])     # 合并转发

# API 调用
self.api.get_group_member_info(user_id)       # 获取群成员信息
self.api.get_image(file_id)                   # 获取图片，返回本地路径
self.api.get_qq_avatar(user_id)               # 获取 QQ 头像 URL
self.api.get_msg(message_id)                  # 获取消息详情
self.api.delete_msg(message_id)               # 撤回消息
self.api.set_essence_msg(message_id)          # 设为精华消息
self.api.delete_essence_msg(message_id)       # 取消精华消息
self.api.set_group_special_title(gid, uid, t) # 设置群头衔
```

**标题注入自动执行:** `send_msg()` 会在 `@` 提及前自动插入用户的装备称号前缀，插件无需手动处理。

---

## Match 方法参考

基类 `Plugin` 提供以下匹配辅助方法。**所有方法必须在 `match()` 中调用，禁止在 `handle()` 中调用。**

### `on_message() → bool`

检查事件类型是否为 `"message"`（消息事件）。

```python
def match(self, event_type):
    return self.on_message() and self.on_full_match("/菜单")
```

### `on_full_match(keyword) → bool`

消息为**单条纯文本**且内容完全匹配 `keyword`。

```python
def match(self, event_type):
    return self.on_full_match("/菜单")
```

匹配规则：
- `self.bot_event.message` 必须恰好有 1 个元素
- 该元素 `type` 必须是 `"text"`
- `data.text.strip()` 必须等于 `keyword`

### `on_full_match_any(*keywords) → bool`

消息为单条纯文本且内容在 `keywords` 集合中。

```python
def match(self, event_type):
    return self.on_full_match_any("/抽奖", "/抽獎", "/抽卡")
```

### `on_begin_with(keyword) → bool`

消息的第一个段是文本且内容等于 `keyword`。

```python
# 匹配 "/打卡" 后跟图片的消息
def match(self, event_type):
    return self.on_begin_with("/打卡")
```

### `on_command(command) → bool`

消息第一个段是文本，按空格分割后首词匹配 `command`。**匹配成功时设置 `self.args`**。

```python
def match(self, event_type):
    return self.on_command("/商店")

def handle(self):
    # self.args = ["/商店", "product_001"]  ← 由 on_command 自动设置
    product_id = self.args[1] if len(self.args) > 1 else None
```

### `on_command_any(*commands) → bool`

同 `on_command`，但首词匹配 `commands` 中任意一个即成功。也设置 `self.args`。

```python
def match(self, event_type):
    return self.on_command_any("/称号", "/稱號")
```

### `super_user() → bool`

检查发送者的 `user_id` 是否在 `SUPER_USER` 列表中。

### `admin_user() → bool`

发送者是 super_user **或** 群内角色为 `"admin"` / `"owner"`。

### 自定义匹配

可以直接访问 `self.bot_event` 的属性实现复杂匹配：

```python
def match(self, event_type):
    if event_type != "message":
        return False
    if self.bot_event.is_private:
        return False
    # 检查是否有回复段 + 特定命令
    has_reply = any(seg.get("type") == "reply" for seg in self.bot_event.message)
    return has_reply and self._command_kind() is not None
```

---

## Constraint: 消息处理模式

### 解析消息段

`self.bot_event.message` 是一个 `list[dict]`，每个元素是 OneBot 消息段：

```python
# 典型消息结构：[{"type": "text", "data": {"text": "hello"}}, {"type": "image", "data": {...}}]

def handle(self):
    for seg in self.bot_event.message:
        if seg.get("type") == "text":
            text_content = seg.get("data", {}).get("text", "")
        elif seg.get("type") == "image":
            image_data = seg.get("data", {})
```

### 提取回复消息 ID

```python
def _extract_reply_id(self):
    """从消息段中提取被回复的消息 ID"""
    for seg in self.bot_event.message:
        if seg.get("type") == "reply":
            msg_id = seg.get("data", {}).get("id")
            if msg_id is not None:
                try:
                    return int(msg_id)
                except (TypeError, ValueError):
                    return None
    return None
```

### 提取命令参数

```python
def _command_kind(self):
    """从消息段中解析指令类型"""
    for seg in self.bot_event.message:
        if seg.get("type") != "text":
            continue
        parts = seg.get("data", {}).get("text", "").strip().split(None, 1)
        if not parts:
            continue
        if parts[0] in ("/加精", "/群精华", "/精华"):
            return "set"
        if parts[0] in ("/删除精华",):
            return "delete"
    return None
```

---

## Constraint: 发送消息

### 基本模式

```python
from core.cq import text, image, at, reply, forward

# 简单文本
self.api.send_msg(text("已设为群精华喵~"))

# 多段消息
self.api.send_msg(reply(msg_id), text("这是回复内容"))

# @某人
self.api.send_msg(at(user_id), text(" 你好"))

# 合并转发（用于长内容）
messages = [text("第一段"), text("第二段"), image(file_path)]
self.api.send_forward_msg(messages)
```

### `send_msg` 自动路由规则

```
group_id 不为 None → 发群聊
user_id 不为 None（且 group_id 为 None）→ 发私聊
两者都为 None → fallback 到 DEFAULT_GROUP_ID 发群聊
```

### 标题注入

`send_msg()` 内部自动调用 `_inject_titles_before_at()`，在 `@` 段前插入用户的称号前缀。**插件不得手动构造称号前缀。**

---

## Constraint: TimedHeartbeatPlugin

继承 `TimedHeartbeatPlugin` 而非 `Plugin` 来实现定时触发。

### 类属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `RUN_AT` | `str` | `"00:00"` | 触发时间，格式 `"HH:MM"`（24 小时） |
| `RUN_WEEKDAYS` | `Optional[Iterable[int]]` | `None` | 限定星期：1=周一 … 7=周日。None 表示不限制 |
| `RUN_ANNUAL_DATES` | `Optional[Iterable[AnnualDateItem]]` | `None` | 限定日期：`(month, day)` 或 `"MM-DD"`。None 表示不限制 |

**过滤逻辑:** `RUN_WEEKDAYS` 和 `RUN_ANNUAL_DATES` 若同时设置，两者都满足时才触发（AND）。

**防重复:** 基于类级别的 `_last_run_minute` 字典，同一分钟内不会重复触发。

### 示例

```python
from core.base import TimedHeartbeatPlugin
from core.utils import register_plugin

@register_plugin
class BackupPlugin(TimedHeartbeatPlugin):
    """每天 08:00 自动备份"""
    name = "backup"
    description = "每日自动备份打卡图片"
    RUN_AT = "08:00"

    def handle(self):
        # 执行备份逻辑
        ...

@register_plugin
class ShopWeeklyRotationPlugin(TimedHeartbeatPlugin):
    """每周一 08:00 刷新商店"""
    name = "shop_weekly_rotation"
    description = "每周一刷新积分商店"
    RUN_AT = "08:00"
    RUN_WEEKDAYS = [1]  # 仅周一

    def handle(self):
        # 刷新商店
        ...
```

### 同时支持定时触发和消息命令

某些插件需要同时响应心跳和用户指令，可以在 `match()` 中组合：

```python
@register_plugin
class FfNewsPlugin(TimedHeartbeatPlugin):
    name = "ff_news"
    description = "FF14 新闻推送"
    RUN_AT = "00:00"  # 每小时整点

    def match(self, event_type):
        # 定时触发 或 手动命令
        return (self.should_run_on_heartbeat(event_type)
                or self.on_full_match("/FF新闻"))
```

---

## Constraint: CommandPlugin

继承 `CommandPlugin` 代替 `Plugin` 来为消息指令插件自动完成指令解析。

### 类属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `COMMANDS` | `str \| tuple[str, ...]` | `()` | 指令前缀列表。设为 `str` 时视为单元素 tuple |

### 自动设置

`match()` 命中后自动设置以下实例属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.cmd` | `str` | 命中的指令前缀（如 `"/商店"`） |
| `self.args` | `list[str]` | 指令后的剩余参数（不含指令本身） |

### 行为细节

- 自动过滤 `event_type != "message"`
- 在消息段中查找首个 `type == "text"` 的段，取其 `data.text` 空格分词后匹配首词
- 支持多段消息（如 `/打卡` + 图片），不要求消息仅含一个文本段
- 继承 `CommandPlugin` 的插件即使不覆写 `match()` 也能正常工作

### 示例

**简单指令（无额外条件）：**

```python
from core.base import CommandPlugin
from core.utils import register_plugin

@register_plugin
class MenuPlugin(CommandPlugin):
    name = "show_menu"
    description = "发送功能菜单"
    COMMANDS = ("/菜单", "/菜單")

    def handle(self):
        self.api.send_msg(text("菜单内容"))
```

**带权限检查的指令（覆写 match）：**

```python
from core.base import CommandPlugin
from core.utils import register_plugin

@register_plugin
class GrantPointsAllPlugin(CommandPlugin):
    name = "grant_points_all"
    description = "全员发积分"
    COMMANDS = ("/发金币", "/發金幣")

    def match(self, event_type="message"):
        return self.admin_user() and super().match(event_type)

    def handle(self):
        amount = int(self.args[0])  # args 不含指令前缀
        ...
```

### 何时不使用

- 非纯文本消息头部的命令（如 `.r3d6` 正则匹配）→ 仍用自定义 `match()`
- 非 `"message"` 事件的处理（notice / meta）→ 仍用 `Plugin`

---

## 反模式清单 (DO NOT)

以下是在本项目中反复出现的 AI/开发者错误，**严禁**：

| # | 反模式 | 正确做法 |
|---|--------|---------|
| 1 | 硬编码指令文本到插件中 | 使用 `plugins/bot_menu_text.py` 的 `BOT_MENU_TEXT` |
| 2 | 在 `match()` 中发送消息或写数据库 | `match()` 只做判断，所有副作用在 `handle()` 中 |
| 3 | 在 `handle()` 中循环调用 `send_msg` 不限制频率 | 合并为转发消息或批处理 |
| 4 | 从一个插件直接 `import` 另一个插件类 | 插件间通过数据库共享状态，不过 `import title.py` 中的纯数据定义是允许的 |
| 5 | 修改 `core/` 模块来添加功能特定逻辑 | 通过插件实现功能，修改 core 需极高审慎 |
| 6 | 在 `match()` 中使用 `self.args` | `self.args` 仅由 `on_command`/`on_command_any` 在匹配成功时设置 |
| 7 | 假设 `self.bot_event.group_id` 始终存在 | 私聊中 `group_id` 为 None，使用前检查 |
| 8 | 在 `handle()` 中创建新的 `DbManager()` | `self.dbmanager` 已在 `__init__` 中创建 |
| 9 | 吞掉异常不记录日志 | 使用 `logger.exception()` 记录，并发送用户友好的错误消息 |
| 10 | 使用 `async`/`await` | 系统是同步的，不要引入 asyncio |
| 11 | 忘记 `@register_plugin` 装饰器 | 缺少装饰器 → 插件静默不工作 |
| 12 | `name` 或 `description` 为空 | 会导致 LLM ToolSpec 转换失败 |
| 13 | 使用 f-string 拼接 SQL | 始终使用参数化查询 `?` 占位符 |
| 14 | 跨 `handle()` 调用在实例属性中存储状态 | 使用数据库或模块级变量 |
| 15 | 修改 `context.plugin_registry` 手动注册 | 始终使用 `@register_plugin` 装饰器 |
