# Spec: 系统架构与事件流

> 关联规范: [plugins.md](plugins.md) | [onebot-protocol.md](onebot-protocol.md) | [conventions.md](conventions.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-06-29

---

## Constraint: 整体架构

```
┌─────────────────────┐
│  OneBot 服务端       │  (NapCat / Lagrange / LLOneBot)
│  ws://127.0.0.1:3001│
└────────┬────────────┘
         │ WebSocket (JSON)
         ▼
┌─────────────────────────────────────────────────┐
│  main.py                                         │
│  ┌──────────────────────────────────────────┐   │
│  │  on_message() 回调                        │   │
│  │  ├── echo 中有 "echo" → Echo.match()     │   │
│  │  └── 否则:                                │   │
│  │       ├── resolve_event_type()            │   │
│  │       └── threading.Thread(plugin_pool)   │   │
│  └──────────────────────────────────────────┘   │
│                                                   │
│  plugin_pool():                                   │
│    for plugin_cls in plugin_registry:             │
│      plugin = plugin_cls(raw_context)             │
│      if plugin.match(event_type):                 │
│        plugin.handle()                            │
└──────────────────────────────────────────────────┘
         │                    │
    ┌────▼────┐         ┌────▼────┐
    │ Thread 1 │  ...    │ Thread N │  (N = len(plugin_registry))
    │ Plugin A │         │ Plugin Z │
    │ match()  │         │ match()  │
    │ handle() │         │ handle() │
    └─────────┘         └─────────┘
```

---

## Constraint: 入口点 (main.py)

`main.py` 是唯一入口，负责：
1. 建立 WebSocket 连接到 OneBot 服务端
2. 注册 `on_message` 回调
3. 掉线自动重连

```python
# 配置（硬编码）
WS_URL = "ws://127.0.0.1:3001"
token = 123456

# WebSocket 连接
api.WS_APP = websocket.WebSocketApp(
    WS_URL,
    header=[f"Authorization: Bearer {token}"],
    on_message=on_message,
)

# 重连循环
while True:
    runtime_context.script_start_time = datetime.now()
    api.WS_APP.run_forever()
    time.sleep(5)  # 断开后等 5 秒重连
```

**MUST NOT:**
- 不应从插件中创建额外的 WebSocket 连接
- 不应修改 `main.py` 的事件分发逻辑来添加特殊处理路径

---

## Constraint: 事件分发模型（一线程每事件每插件）

每个 OneBot 事件触发时，`on_message` 回调执行：

```python
def on_message(_, message):
    context = json_.loads(message)
    if "echo" in context:
        api.echo.match(context)        # API 响应 → 匹配等待队列
    else:
        event_type = resolve_event_type(context)
        t = threading.Thread(          # 新线程处理
            target=plugin_pool,
            args=(context, event_type)
        )
        t.start()
```

`plugin_pool()` 遍历所有已注册插件：

```python
def plugin_pool(context, event_type):
    for plugin_cls in runtime_context.plugin_registry:
        plugin = plugin_cls(context)
        if plugin.match(event_type):
            plugin.handle()
```

**关键属性:**
- 每个事件触发 N 个线程（N = 已注册插件数）
- 每个线程创建一个新的插件实例
- 插件之间**无执行顺序保证**
- 插件之间**无同步机制**（需自行处理并发）

---

## Constraint: 事件类型解析

```python
def resolve_event_type(context):
    if "meta_event_type" in context:
        return "meta"       # 心跳/生命周期
    if context.get("post_type") == "notice":
        return "notice"     # 通知（加群/退群/撤回等）
    return "message"        # 消息（群聊/私聊）
```

| event_type | post_type | 典型场景 | 有 message 字段 |
|------------|-----------|---------|----------------|
| `"meta"` | `"meta_event"` | 心跳、连接生命周期 | 否 |
| `"notice"` | `"notice"` | 群成员变动、消息撤回、好友添加 | 否 |
| `"message"` | `"message"` | 群聊消息、私聊消息 | **是** |

---

## Constraint: 模块依赖关系

```
main.py
 ├── core.api          (WS_APP, Echo 单例)
 ├── core.context      (plugin_registry, 路径常量)
 ├── core.logger       (全局 logger)
 └── plugins           (触发自动发现 → 注册所有插件)
       └── core.base    (Plugin, CommandPlugin, TimedHeartbeatPlugin)
           ├── core.event      (Event 包装器)
           ├── core.api        (ApiWrapper — 每个插件实例一个)
           ├── core.cq         (消息段构造器)
           └── core.database_manager  (DbManager — 每个插件实例一个)
                └── core.context (路径常量)

core.llm.*            ← LLM 子系统（独立分层，见 llm-subsystem.md）
core.gen_image.*      ← 图片生成（独立，见 image-generation.md）
checkin_gallery/*     ← Web 应用（独立进程，见 web-gallery.md）
```

**循环导入:** 目前存在以下循环关系（已知，不轻易打破）:
- `core.base` → `core.api` → `core.event` (ok, event 无反向依赖)
- `core.api` 在方法内延迟导入 `plugins.title`（`_build_title_prefix` 中）

---

## Constraint: 插件自动发现链

```
main.py: import plugins
    └── plugins/__init__.py: _load_all_plugin_modules()
        └── pkgutil.walk_packages("plugins")
            └── 对每个子模块: importlib.import_module(name)
                └── 模块级代码执行
                    └── @register_plugin 装饰器触发
                        └── context.plugin_registry.append(cls)
```

**MUST:**
- `main.py` 必须执行 `import plugins`（否则没有插件被注册）
- 插件模块必须放在 `plugins/` 目录下（不支持子目录）
- `@register_plugin` 是注册的唯一方式

**MUST NOT:**
- 手动 `plugin_registry.append()` 绕过装饰器
- 在 `plugins/__init__.py` 之外做自动发现

---

## Constraint: WebSocket 生命周期

```
启动 → run_forever() → [连接中] → on_open → [工作中] → 断开
                                                          ↓
                                              sleep(5) → run_forever() → ...
```

- `script_start_time` 在每次重连时更新
- 断开期间的所有 API 调用会超时（30 秒）返回 `{}`
- `startup_changelog_sent` 在首次连接时发送启动通知

---

## Constraint: 线程安全边界

| 组件 | 线程安全性 | 说明 |
|------|-----------|------|
| `DbManager` 实例 | **非线程安全** | 每个实例有独立的 `sqlite3.Connection`；不要跨线程共享同一个实例 |
| `sqlite3` 写锁 | 安全 | sqlite3 自身通过文件锁序列化写操作，多个连接并发写是安全的 |
| `Echo.echo_list` (deque) | 安全 | `collections.deque` 的 `append`/迭代是线程安全的 |
| `Queue` | 安全 | `queue.Queue` 是线程安全的 |
| `context.plugin_registry` | **只读安全** | 仅在导入期间写入，运行时只读 |
| `context.script_start_time` | **只读安全** | 仅在主线程中写入 |
| `TimedHeartbeatPlugin._last_run_minute` | **需注意** | 类级字典，多线程读写；依赖 GIL 保护单个字典操作 |

**MUST:**
- 不要在插件之间共享 `DbManager` 实例
- 不要跨线程共享可变状态（用数据库代替）
- 如果必须在插件间共享状态，使用 `threading.Lock`

---

## Constraint: Echo 异步响应机制

API 调用通过 echo 机制实现异步请求-响应：

```python
# Echo 类
class Echo:
    def __init__(self):
        self.echo_num = 0
        self.echo_list = collections.deque(maxlen=20)

    def get(self):
        self.echo_num += 1
        q = queue.Queue(maxsize=1)
        self.echo_list.append((self.echo_num, q))
        return self.echo_num, q

    def match(self, context):
        for obj in self.echo_list:
            if context["echo"] == obj[0]:
                obj[1].put(context)  # 放入队列，解除阻塞
```

流程：
1. `call_api()` 调用 `echo.get()` → 获得 `(echo_num, Queue)`
2. 发送 JSON: `{"action": ..., "params": ..., "echo": echo_num}`
3. 在 `Queue.get(timeout=30)` 上阻塞等待
4. OneBot 返回响应时，`on_message` 匹配 `echo` 字段，将响应放入对应队列
5. `call_api()` 获得响应，返回给调用者

**限制:** `deque(maxlen=20)` 限制同时最多 20 个未完成的 API 调用。
