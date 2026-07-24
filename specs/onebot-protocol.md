# Spec: OneBot v11 协议与消息构造

> 关联规范: [architecture.md](architecture.md) | [plugins.md](plugins.md) | [conventions.md](conventions.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-06-29

---

## Constraint: 协议概述

- **协议版本:** OneBot v11
- **通信方式:** WebSocket（正向连接，bot 作为客户端连接服务端）
- **服务端兼容:** NapCat、Lagrange、LLOneBot
- **传输格式:** JSON
- **官方文档:** https://github.com/botuniverse/onebot-11

---

## Constraint: 事件结构

### 消息事件 (post_type = "message")

```json
{
    "time": 1712345678,
    "self_id": 3915014383,
    "post_type": "message",
    "message_type": "group",       // "group" | "private"
    "sub_type": "normal",
    "message_id": 12345,
    "user_id": 1057613133,
    "group_id": 296470819,         // 仅群聊
    "message": [
        {"type": "text", "data": {"text": "hello"}},
        {"type": "image", "data": {"file": "xxx", "url": "xxx"}}
    ],
    "raw_message": "hello",
    "sender": {
        "user_id": 1057613133,
        "nickname": "用户名",
        "card": "群名片",
        "role": "member"           // "owner" | "admin" | "member"
    }
}
```

**属性对应 (Event 类):**
| JSON 字段 | Event 属性 | 类型 |
|-----------|-----------|------|
| `user_id` | `.user_id` | `int \| None` |
| `group_id` | `.group_id` | `int \| None` |
| `message` | `.message` | `list[dict]` |
| `message_id` | `.message_id` | `int \| None` |
| `message_type` | `.is_group` / `.is_private` | `bool` |
| `post_type` | `.post_type` | `str \| None` |
| `sender` | `.sender` | `dict \| None` |
| `time` | `.time` | `int \| None` |

### 通知事件 (post_type = "notice")

```json
{
    "post_type": "notice",
    "notice_type": "group_recall",  // 子类型
    "user_id": 1057613133,
    "group_id": 296470819,
    // ... 根据 notice_type 有不同的额外字段
}
```

常见 `notice_type`:
- `group_recall` — 群消息撤回
- `friend_add` — 好友添加成功
- `group_increase` / `group_decrease` — 群成员变动

### 元事件 (meta_event_type 存在)

```json
{
    "meta_event_type": "heartbeat",  // 或 "lifecycle"
    "self_id": 3915014383,
    "time": 1712345678,
    "status": { ... },
    "interval": 5000
}
```

---

## CQ 码 / 消息段构造器

所有构造器位于 `core/cq.py`。每个返回一个 `dict`，可直接传给 `send_msg()`。

### `text(string: str) → dict`
```python
text("你好")  # → {"type": "text", "data": {"text": "你好"}}
```

### `image(file: str) → dict`
```python
image("file:///path/to/img.png")  # 本地文件
image("http://example.com/a.jpg") # URL
image(file_id)                     # 从 get_image() 获取的 file_id
# → {"type": "image", "data": {"file": "..."}}
```

### `at(qq: int) → dict`
```python
at(1057613133)  # → {"type": "at", "data": {"qq": 1057613133}}
```

### `at_all() → dict`
```python
at_all()  # → {"type": "at", "data": {"qq": "all"}}
```

### `reply(id: str) → dict`
```python
reply("12345")  # → {"type": "reply", "data": {"id": "12345"}}
```
**注意:** `id` 参数类型是 `str`，传入时必须转换。

### `forward(messages: list) → list`
```python
forward([text("段落1"), image("file.png")])
# → [{"type": "node", "data": {"content": [...]}}]
```
合并转发消息的包装函数。传给 `send_group_forward_msg()` 等使用。

### 其他分段
```python
record("file.amr")       # 语音
xml("<xml>...</xml>")    # XML 消息
json('{"app":"..."}')    # JSON 卡片
music("123456")          # QQ 音乐分享
```

---

## Constraint: send_msg 自动路由

`ApiWrapper.send_msg()` 自动判断发送目标：

```python
def send_msg(self, *message):
    message = self._inject_titles_before_at(message)  # 自动注入称号
    if self.context.group_id is not None:
        return self.send_group_msg(*message)          # 群聊
    elif self.context.user_id is not None:
        return self.send_private_msg(*message)        # 私聊
    else:
        return self.send_group_msg(*message)          # fallback
```

`send_group_msg()` 在 `group_id` 为 `None` 时 fallback 到 `DEFAULT_GROUP_ID`。

---

## Constraint: 标题注入

`send_msg()` 内部自动调用 `_inject_titles_before_at()`：

```python
def _inject_titles_before_at(self, message):
    merged = []
    for seg in message:
        if isinstance(seg, dict) and seg.get("type") == "at":
            qq = seg.get("data", {}).get("qq")
            if qq != "all":
                prefix = self._build_title_prefix(qq)
                if prefix:
                    merged.append(text(prefix + " "))
        merged.append(seg)
    return tuple(merged)
```

- 仅对 `at` 类型的段注入（不对 `at_all` 注入）
- 称号前缀格式: `「称号1·称号2·称号3」`
- 最多显示 3 个装备称号
- **插件不应手动构造称号前缀**

---

## Constraint: API 方法参考

所有 API 方法封装在 `core/api.py` 的 `ApiWrapper` 类中。

### 消息发送

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `send_msg` | `(*message) → int` | message_id，失败返回 0 | 自动路由 |
| `send_group_msg` | `(*message) → int` | message_id，失败返回 0 | 强制群聊 |
| `send_private_msg` | `(*message) → int` | message_id，失败返回 0 | 强制私聊 |
| `send_forward_msg` | `(message: list) → int` | 1 成功 / 0 失败 | 合并转发，自动路由 |
| `send_group_forward_msg` | `(message: list) → int` | 1 成功 / 0 失败 | 群合并转发 |
| `send_private_forward_msg` | `(message: list) → int` | 1 成功 / 0 失败 | 私聊合并转发 |

### 消息操作

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_msg` | `(message_id) → dict` | 消息详情，失败返回 `{}` | |
| `delete_msg` | `(message_id: int) → bool` | | 撤回消息 |

### 精华消息（扩展 API）

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `set_essence_msg` | `(message_id: int) → bool` | | 设为精华 |
| `delete_essence_msg` | `(message_id: int) → bool` | | 取消精华 |

### 群组/成员

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_group_member_info` | `(user_id) → dict` | | 获取群成员信息 |
| `set_group_special_title` | `(group_id, user_id, title) → int` | | 设置群头衔 |
| `get_group_album_list` | `(group_id) → list` | | 获取群相册列表 |

### 图片/资源

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_image` | `(file) → str` | 本地文件路径，失败返回 `""` | |
| `get_image_url` | `(file) → str` | URL，失败返回 `""` | |
| `get_qq_avatar` | `(user_id) → str` | 头像 URL，失败返回 `""` | 扩展 API |

### 好友请求

| 方法 | 签名 | 说明 |
|------|------|------|
| `set_friend_add_request` | `(flag, approve=True)` | 处理好友请求 |

### 底层调用

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `call_api` | `(action: str, params: dict) → dict` | API 响应 | 30 秒超时返回 `{}` |

---

## Constraint: 返回值检查

```python
# send_msg / send_group_msg 等 → 检查 > 0
msg_id = self.api.send_msg(text("hello"))
if msg_id == 0:
    logger.error("发送失败")

# 布尔返回 → 直接检查
if self.api.set_essence_msg(message_id):
    self.api.send_msg(text("已加精喵~"))

# 字符串返回 → 检查非空
avatar_url = self.api.get_qq_avatar(user_id)
if avatar_url:
    # 使用 URL

# call_api → 检查 status
ret = self.api.call_api("some_action", params)
if ret.get("status") == "ok":
    data = ret.get("data", {})
```

**失败时返回的哨兵值:**
- 整数方法 → `0`
- 布尔方法 → `False`
- 字符串方法 → `""`
- 字典方法 → `{}`
- `call_api` → `{}`（超时）或 `{"status": "failed"}`
