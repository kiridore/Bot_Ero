# 开发规范与注意事项

> 硬性约束、AI 检查清单、技术债、常见陷阱

---

## 硬性约束

- **禁止 async/await** — bot 进程纯同步、多线程（例外：webapp/FastAPI 的 middleware/route 用 async 是合法的，不要把两套风格混进同一进程）
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
- 配置半环境变量化：路径/盐/端口/开关等约 30 个 `BOTERO_*` 环境变量集中在 `core/config.py`，`scripts/botero.env` 是部署侧单一来源；但 WS 地址/token、默认群号、超级用户、下载代理等仍硬编码在源码（见 `kb/QUICK_REFERENCE.md` 硬编码常量表）
- 无迁移框架，Schema 演化依赖手动 PRAGMA + ALTER
- 无测试框架，`test/` 下是临时测试脚本
- 部分旧表 (user_title_state, group_alarms repeat_y/m/d) 已被新设计取代但未删除
- `core/api.py` 延迟导入 `plugins.title` 存在循环依赖
- `webapp/__main__.py` 的 `--db` 参数不生效：`core.config.DB_PATH` 在模块首次 import 时冻结，`main()` 里设 env 太晚；需启动前注入 env（`BOTERO_DB_PATH=...`）

## 安全注意

- Web 图库登录密钥盐单一来源：`scripts/botero.env`（bot 的 main.py 启动加载，webapp 经 systemd EnvironmentFile；源码默认值与其一致）
- `AUTH_SALT` 改变会导致所有已发出的登录密钥失效（换盐用 `BOTERO_AUTH_SALT_OLD` 无感迁移）
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

## 时间线开发经验（2026-08-10）

### 陷阱 1：全局 `main` 规则会让 grid 列收缩到内容宽（最难排查）

`core/web/static/gallery.css` 有全局规则：

```css
main { padding: 12px 16px 3rem; max-width: 1600px; margin: 0 auto; }
```

任何 `<main>` 元素都会继承。若它同时是 **grid 项**，`margin: 0 auto` 会覆盖 `justify-self: stretch`——自动外边距吸收剩余空间后，该项收缩到**内容宽度**并在轨道内居中。结果：列宽 = 最长一行文本宽度，标题短 → 列窄 → 卡片窄，与固定列宽的预期完全不符（表现为"元素宽度跟随内容"）。

修复（`webapp/static/timeline.css`）：

```css
.tl-main {
  min-width: 0;
  margin: 0;        /* 关键：清掉 auto 外边距，恢复 stretch */
  max-width: none;
  padding: 0;
}
```

排查要点：DevTools 勾掉 `margin: 0 auto` 立即恢复，即查全局元素选择器（`main`/`div`/`section`）+ auto 外边距。

### 陷阱 2：`--db` 启动参数不生效（见"已知技术债"）

`core.config.DB_PATH` 在模块首次 import 时求值冻结，`webapp/__main__.py` 的 `main()` 里设 env 太晚 → `--db` 静默无效，测试数据可能写进真实 `data.db`。正确隔离：进程启动前注入 env：`BOTERO_DB_PATH=/tmp/x.db python3 -m webapp`。

### 陷阱 3：`hub restart` 复用旧启动规格

改 env/args 必须 `stop` 后重新 `start`，否则沿用旧参数（曾导致测试实例连错数据库）。

### 陷阱 4：dedup_key 粒度必须等于业务动作粒度

`timeline_events` 表 `UNIQUE(source, dedup_key)` + `INSERT OR IGNORE`——重复提交**静默丢弃**（HTTP 200，响应 `inserted: false`）。打卡事件最初用 `checkin:<user>:<日期>`，隐含"一天一次"假设；实际同一天多次打卡合法（每次独立记录），第二次事件被唯一约束吞掉。

教训：
- 业务自然键按**动作实例**设计，不按周期：`checkin:<user_id>:<YYYY-MM-DD>:<message_id>`
- 排查"事件没上卡片"先看 POST 响应 `inserted` 字段（`false` = 被去重吞掉）
- 撤回/回滚必须能由发送方推导同一 key：打卡/撤回打卡/消息撤回三处共用同一构造规则

### 模式 1：`{id:}` 占位符 + 渲染时解析

昵称/头像不在发送方烘焙进文案（QQ 改名 → 旧数据永远错）；协议支持 `{id:<user_id>}` 占位符，接收方渲染时经 `resolve_display_name`/`resolve_avatar_url` 解析；未绑定 → 「未绑定玩家」。

### 模式 2：keyset 分页（硬删除免疫）

硬删除（撤回）下 offset 分页会翻页错位；时间线用 `(received_at DESC, id DESC)` keyset 游标，对删除免疫。

### 模式 3：浏览器不可用时的前端验证

本环境 Chromium 缺系统库（libnspr4/libnss3，WSL2 无 sudo）无法 headless。替代：
- 最小 DOM stub + node eval（`test/test_timeline_render.js`，复刻 `test_auth_render.js` 模式；eval 作用域隔离需 `global.X = window.X` 桥接）
- 线上/本地对比：`curl https://littlero.tech/static/<file> | md5sum` 与本地比对，排除部署/缓存差异（生产 css/js 与本地一致即可信任本地结论）

### 模式 4：测试隔离

webapp 冒烟必须用进程启动前注入的 `BOTERO_DB_PATH` 指向临时库；测完清理残留行（`DELETE FROM timeline_events WHERE id IN (...)`），防止测试数据污染生产表。
