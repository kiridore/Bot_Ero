# Spec: 插件开发契约

> 关联规范: [conventions.md](conventions.md) | [plugin-catalog.md](plugin-catalog.md) | [onebot-protocol.md](onebot-protocol.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-08-09 (插件目录结构同步：每插件一个文件夹)

---

## Constraint: 同步通知与统一消息输出（迁移中）

- 每次外部事件由 `Operation` 持有独立内部通知和输出列表；消费者在同一线程执行，不直接递归调用别的插件。
- `subscribe` 必须声明所属插件。加载时登记并不意味着启用；运行时按本次操作的开关快照筛选。`cleanup` 仅供根据实际历史奖励撤销的处理，不得用于新奖励绕过开关。
- 处理成功后才接收其子通知和消息；异常时丢弃尚未确认输出并继续其他处理。数据库事务由业务处理负责，通知模块不声称可以回滚已经完成的外部副作用。
- 迁移后的插件通过 `submit_message` 或本次操作的输出模块提交请求。纯文本可带合并标记和显示顺序；同一次操作、同一接收方、相同非空标记才可合并；无标记和特殊消息独立发送。禁止拼入其他用户或其他群的消息。
- 消息输出是必需模块，不是可关闭插件；发送失败不得重新执行业务或自动重发结果不明的消息。同一输出列表只能绑定一个操作，重复执行最终发送不会再次发消息。错误日志包含操作标识、批次、分段、类型和目的地，可与事件开始日志关联；面向用户的失败提示不包含异常原文。
- 已迁移入口包括打卡及撤回、单抽/一键抽奖、周常查询、称号管理、商店查询/兑换与手动/定时刷新。一键抽奖各插件提示通过forward_text请求带合并标记和节点序号，由输出模块构造最终节点，不由抽奖插件调用其他插件拼接文案。通知循环检查按类型与业务来源识别，另有每事件1000条安全上限。普通提示提交消息段，原合并转发使用 `kind="forward"` 保留结构。无默认接收方的商店定时刷新仍更新货架但不提交公告；兑换内部异常只写日志，不回显给用户。
- 新旧发送方式仅在迁移期间共存：未迁移插件继续调用旧 API；已迁移插件只提交输出请求，禁止同时直接发送。`test/test_plugin_send_compatibility.py` 验证真实发送适配器、兼容入口和已迁移文件无旧发送调用。
- 私聊账号设置只有超级用户可以修改；账号默认继承公共设置，明确关闭不能通过删除行表示。系统插件不支持账号关闭覆盖。
- 本次允许私有版独立关闭语义改变，但第一阶段未迁移的旧插件暂时保持原发送方式。完成全部插件迁移后才能移除兼容路径。

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
| 1 | 硬编码指令文本到插件中 | 使用 `plugins/menu/bot_menu_text.py` 的 `BOT_MENU_TEXT` |
| 2 | 在 `match()` 中发送消息或写数据库 | `match()` 只做判断，所有副作用在 `handle()` 中 |
| 3 | 在 `handle()` 中循环调用 `send_msg` 不限制频率 | 合并为转发消息或批处理 |
| 4 | 从一个插件直接 `import` 另一个插件类 | 插件间通过数据库共享状态，不过 `from plugins.title import TITLE_DEFS` 等纯数据定义是允许的 |
| 5 | 修改 `core/` 模块来添加功能特定逻辑 | 通过插件实现功能，修改 core 需极高审慎 |
| 6 | 在 `match()` 中使用 `self.args` | `self.args` 由 `on_command`/`on_command_any` 或 `CommandPlugin` 在匹配成功时设置 |
| 7 | 假设 `self.bot_event.group_id` 始终存在 | 私聊中 `group_id` 为 None，使用前检查 |
| 8 | 在 `handle()` 中创建新的 `DbManager()` | `self.dbmanager` 已在 `__init__` 中创建 |
| 9 | 吞掉异常不记录日志 | 使用 `logger.exception()` 记录，并发送用户友好的错误消息 |
| 10 | 使用 `async`/`await` | 系统是同步的，不要引入 asyncio |
| 11 | 忘记 `@register_plugin` 装饰器 | 缺少装饰器 → 插件静默不工作 |
| 12 | `name` 或 `description` 为空 | 会导致 LLM ToolSpec 转换失败 |
| 13 | 使用 f-string 拼接 SQL | 始终使用参数化查询 `?` 占位符 |
| 14 | 跨 `handle()` 调用在实例属性中存储状态 | 使用数据库或模块级变量 |
| 15 | 修改 `context.plugin_registry` 手动注册 | 始终使用 `@register_plugin` 装饰器 |

---

## 附录：心跳任务多群作用域审计（社区版 T0.9，2026-10-06；作用域修复 2026-10-09 config-unification 任务组3）

> 审计范围：全部 `TimedHeartbeatPlugin` 子类 + 手动分钟/秒级去重的 meta 触发插件。原三栏归类已被 config-unification 统一规则取代：**部署许可（`bot.allowed_plugins`）+ 按任务所属群/账号的局部开关**，不再有“私有专属/社区白名单”两套路径。

| 插件 | 触发 | 归类 | 依据 / 风险 |
|---|---|---|---|
| `shop_weekly_rotation`（redeem_shop） | meta · 周一 08:00 | **全局单次（现状即可）** | `shop_stock` 表全局单份（无 group 维度，logic.py 注释明确"数据库 shop_stock 为唯一货架"），轮换单次执行正确。社区形态下货架公告经 `send_msg` 无群上下文 → T0.2 兜底丢弃（WARNING 日志），**货架刷新本身不受影响**；按群公告（iter_active_groups 遍历）留批次 2 |
| `weekly_quest_reset`（weekly_quest） | meta · 周一 08:00 | **全局单次（现状即可）** | 纯 DB 清理（`quest.cleanup_old`），无消息发送，社区两默认包均含 |
| `backup` | meta 心跳 + `/数据备份` 指令 | **全局单次（现状即可）** | 全库备份与形态无关，社区同样需要 |
| `forum_notify` | meta · 每分钟（手动分钟去重，Plugin 子类） | **全局单次（现状即可）** | 轮询 forum 表；社区批次 1 不带 webapp/forum，表恒空 → handle 天然 no-op，无害 |
| `ff_news` | meta · 整点 | **私有专属（不进社区）** | FF14 官网新闻推默认群。⚠️ 见下方"meta 路径泄漏" |
| `weekly_report` | meta · 启动补偿 + 周一 08:00 | **私有专属（不进社区）** | 数据源 message_log（社区不启用 message_logger）；周报发默认群。⚠️ 同上 |
| `startup_changelog` | meta · 启动首次（Plugin 子类，`startup_changelog_sent` 标志） | **私有专属（不进社区）** | ⚠️ 同上 |
| `welcome` / `auto_friend` | notice / request 触发 | 不属心跳 | M1 由 register 插件承接（T1.3） |
| `activity_timer`（activity） | 消息事件驱动（Plugin 子类，非心跳） | 需按群遍历（批次 2） | 自带 `activity.group_id`（23 处引用），多群并发审计归 B2.2 |

### 2026-10-09 修复现状（config-unification 任务组3）

- `main.py::plugin_pool` 对 meta 事件不再绕过门控：先过部署许可（`plugin_allowed`），局部开关由各任务按所属对象自查（`context.effective_for_scope`）。
- 按所属对象过滤（检查先于发送/状态推进/结算）：`group_alarm`（私聊查创建者账号、群聊查所属群）、`activity_timer`（活动所属群）、`immortal_lottery` 开奖（下注群；已付注单保留并 WARNING 可定位）。
- 目的地过滤：商店公告（目标群未启用不发，货架照常刷新）、`ff_news`（无有效目标不请求官网）、`forum_notify`（不发送不标记已通知，帖子保留）、`weekly_report`（目标群未启用不生成不通知）。
- 共享维护任务（货架刷新、`weekly_quest_reset` 清理、`backup`）只受部署许可控制，不因单群关闭而停。
- 关闭不删记录：闹钟/注单/帖子/活动状态保留，重新开启后按原到期规则处理；重复执行防护（fired 标志/开奖结果唯一）不变。详见 `openspec/changes/config-unification/` 与 `test/test_scoped_heartbeats.py`、`test/test_heartbeat_pending_tasks.py`。
- 历史注记：下方“meta 路径泄漏”发现已被上述修复取代，双形态白名单方案已废弃（仅配置差异原则）。

### 原 2026-10-06 审计记录（历史）

`main.py::plugin_pool` 对 **meta 事件绕过 `is_plugin_enabled`**（`event_type != "meta" and not ...`），因此：

- T0.4（`bot.system_plugins` 配置）与 T0.7（功能包按群开关）**都管不到 meta 路径**——development-plan 原"T0.4/T0.7 排除 ff_news/startup_changelog"的假设对 meta 触发插件不成立；
- 社区形态下 `ff_news`（整点抓取+发送）、`weekly_report`（聚合+发送）、`startup_changelog`（启动播报）仍会被 meta 心跳触发：外呼/聚合白白执行，发送被 T0.2 兜底丢弃并刷 WARNING——**功能无害但属资源浪费与日志噪音**；
- 修复归属 **M1 T1.2 中央门控**：门控设计需从"meta 事件跳过全部门控"修正为"社区形态下 meta 事件经插件级白名单过滤——仅社区必需心跳（`shop_weekly_rotation`/`weekly_quest_reset`/`backup`/`forum_notify`）与社区系统插件可见，私域 meta 插件不可见；私有形态 meta 直通不变（红线 #122）"。属双形态接缝白名单第 4 处（plugin_pool 中央门控），合法。

### 批次 1 结论

批次 1 范围内（shop_weekly_rotation + weekly_quest_reset）**零问题、零代码改动**；唯一发现（meta 泄漏）修复归属 T1.2，已回写 development-plan T1.2 节。
