# 部署与运维

> 部署方式、API 速查、外部 API、版本历史

---

## 部署

### 裸机 Python 部署

```bash
python main.py
```

依赖: `websocket-client` `requests` `Pillow`
可选: `psutil` (系统监控) `GitPython` (更新) `openai` (LLM，已弃用)

### Web 应用部署

```bash
export BOTERO_AUTH_SALT="your-secret-salt"
export BOTERO_ONEBOT_HTTP="http://..."
python -m webapp
```

单进程承载导航主页（`/`）与 6 个功能分区（`/gallery` `/guestbook` `/profile` `/trpg` `/alarms` `/activities`），Caddy 全量反代 8765，单一根域按路径路由。完整部署见 `docs/web-apps-deployment.md`。

## 备份机制

- 每天 08:00 自动备份: 下载打卡图片到 `server_data/record_images/<user_id>/`
- 手动备份: 群内发 `/数据备份`

## 更新流程

超级用户发 `/更新` → `git pull` → 有新 commit 则 `os.execv()` 重启进程

## WebSocket 重连

断开后等 5 秒自动重连，`script_start_time` 更新。

---

## API 调用速查

### 发送消息

```python
self.api.send_msg(text("..."), at(uid), image(file))
self.api.send_group_msg(*segments)
self.api.send_private_msg(*segments)
self.api.send_forward_msg([segments_list])
```

**send_msg 自动路由:**
```python
self.api.send_msg(text("回复"))
# group_id != None → 发群聊
# 只有 user_id    → 发私聊
# 两者皆无        → fallback 到 DEFAULT_GROUP_ID
```

**标题自动注入:** `send_msg()` 内部自动在 `@` 段前注入用户装备称号，格式 `「称号1·称号2·称号3」@用户`。**插件严禁手动构造称号前缀。**

### 获取信息

```python
self.api.get_group_member_info(user_id)     # 群成员信息
self.api.get_image(file_id)                 # 图片本地路径
self.api.get_image_url(file_id)             # 图片 URL
self.api.get_qq_avatar(user_id)             # 头像 URL
self.api.get_msg(message_id)                # 消息详情
```

### 消息操作

```python
self.api.delete_msg(message_id)             # 撤回消息
self.api.set_essence_msg(message_id)        # 加精
self.api.delete_essence_msg(message_id)     # 取消加精
```

### 群管理

```python
self.api.set_group_special_title(gid, uid, title)  # 设群头衔
self.api.get_group_album_list(gid)                  # 群相册
```

### 好友

```python
self.api.set_friend_add_request(flag, approve=True)
```

### 底层

```python
self.api.call_api("action_name", {params})  # 原始 API，30s 超时
```

### CQ 消息段构造器 (`core/cq.py`)

```python
text("文本")          # {"type": "text", "data": {"text": "文本"}}
image("file:///...")  # {"type": "image", "data": {"file": "..."}}
at(qq_number)         # {"type": "at", "data": {"qq": qq_number}}
at_all()              # {"type": "at", "data": {"qq": "all"}}
reply(msg_id)         # {"type": "reply", "data": {"id": str(msg_id)}}
forward(messages)     # [{"type": "node", "data": {"content": [...]}}]
```

### API 返回值检查

失败哨兵值:
- 整数方法 → `0`
- 布尔方法 → `False`
- 字符串方法 → `""`
- 字典方法 → `{}`
- `call_api` 超时 → `{}`

---

## 外部 API 清单

| API | URL | 用途 |
|-----|-----|------|
| OneBot WS | `ws://127.0.0.1:3001` | QQ 消息收发 |
| FF14 新闻 | `https://cqnews.web.sdo.com/api/news/newsList` | 新闻拉取 |
| picsum.photos | `https://picsum.photos/512` | 随机参考图 |
| DeepSeek (弃用) | `https://api.deepseek.com` | LLM 对话 |
| SiliconFlow (弃用) | `https://api.siliconflow.cn` | 嵌入向量 |

---

## 版本历史

| 版本 | 内容 |
|------|------|
| 1.0 | 打卡、打卡查询、历史图查询、板油查询 |
| 1.1 | 撤回打卡、服务器状态、免 @ 打卡 |
| 1.2 | 年度/月度热力图、指令重启更新 |
| 1.3 | 周一到周一八点、自动同意好友 |
| 1.4 | 全量打卡图合并转发、数据迁移 |
| 1.5 | 补卡功能 |
| 1.6 | 积分兑换系统 |
| 1.7 | 定时插件系统、修复丢失图片 |
| 1.8 | 单日补卡、更多积分消费、称号系统 |
| 2.0 | 计划: 日志系统、事件队列重构、LLM 重构 … |
| 2.1 | 未定义 |
