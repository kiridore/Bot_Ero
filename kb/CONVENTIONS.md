# 开发规范与注意事项

> 硬性约束、AI 检查清单、技术债、常见陷阱

---

## 硬性约束

- **禁止 async/await** — 纯同步，多线程
- **禁止 f-string SQL** — 必须用 `?` 参数化查询
- **禁止相对导入** — 插件间用绝对导入
- **match() 禁止副作用** — 不发消息、不写数据库
- **handle() 必须有 try/except** — 否则线程异常静默死掉
- **周相关必须用 08:00 偏移** — `get_monday_to_monday()`
- **新增/改名指令必须更新 `plugins/menu/bot_menu_text.py`** — 同一 commit
- **代码变更必须更新对应 spec** — 同一 commit
- **禁止在插件间导入业务逻辑类** — 导入纯数据/函数允许

## 周边界 (08:00 偏移)

**一"周" = 周一 08:00 → 下周一 08:00**，不是自然周 00:00。

使用 `core/utils.py:get_monday_to_monday()`:

```python
from core.utils import get_monday_to_monday
start, end = get_monday_to_monday()
# start = "2026-07-20 08:00:00"
# end   = "2026-07-27 08:00:00"
```

**同样使用 08:00 偏移的:**
- `utils.day_of_year()` — 热度图日期索引
- `database_manager.get_user_streaks()` — 连续打卡天数
- `webapp/gallery/dates.py` — Web 端结算日

**新增任何"周"相关功能必须使用此函数。**

## 日志与错误处理

```python
from core.logger import logger
logger.info("...")
logger.error("...")
logger.exception("...")  # 自动附带 traceback
```
格式: `[bot] %(asctime)s - %(levelname)s - %(message)s`，级别 INFO。

## 常见 AI 错误预防清单

1. 新增插件 → 加 `@register_plugin` 了吗？
2. 新增指令 → 更新 `BOT_MENU_TEXT` 了吗？
3. `handle()` → 有 try/except 吗？
4. 数据库 → 参数化查询 `?` 了吗？
5. 新表/列 → `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` 了吗？
6. 周逻辑 → 用了 08:00 偏移吗？
7. `self.bot_event.group_id` → 检查 None 了吗？
8. `self.args` → `match()` 中调了 `on_command` 吗？
9. 新依赖 → 记录了吗？
10. `async`/`await` → 确认没引入？
11. 新增插件 → 新群默认禁用，是否通知管理员手动启用？
12. 新增系统插件 → 加入 `SYSTEM_PLUGINS` 了吗？（`core/context.py`）
13. `plugin_pool` 修改 → `is_plugin_enabled` 检查是否有 `sqlite3.Error` 兜底？

## 已知技术债

- `user_id` 在数据库中类型不一致（TEXT vs INTEGER），跨表查询需 CAST
- 无配置文件，所有设置硬编码在源码中
- 无迁移框架，Schema 演化依赖手动 PRAGMA + ALTER
- 无测试框架，`test/` 下是临时测试脚本
- 部分旧表 (user_title_state, group_alarms repeat_y/m/d) 已被新设计取代但未删除
- `core/api.py` 延迟导入 `plugins.title` 存在循环依赖

## 安全注意

- Web 图库的 `AUTH_SALT` 默认值在 repo 中，生产必须通过环境变量覆盖
- `AUTH_SALT` 改变会导致所有已发出的登录密钥失效
- 下载代理 `127.0.0.1:7890` 硬编码，非标准端口

## 路径陷阱

- `context.python_data_path` (`"./server_data"`) vs `context.llonebot_data_path` (`"/app/llonebot/server_data"`)
- 用在 Python 文件 I/O 用前者，传给 OneBot API 用后者
- 用错不会报错，只会返回空/失败 — **极难排查**

## 线程模型陷阱

- Plugin 实例**每次事件都是全新的** — 不能依赖实例属性持久化状态
- 多个 Plugin 实例同时操作数据库 — 靠 SQLite 文件锁
- `TimedHeartbeatPlugin._last_run_minute` 是类级字典，依赖 GIL 保护
- 不要在插件间共享 `DbManager` 实例
