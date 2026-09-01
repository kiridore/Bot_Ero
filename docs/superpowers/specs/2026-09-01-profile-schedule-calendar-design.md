# 个人主页日程日历（/profile/schedule）— 设计文档

- 日期：2026-09-01
- 状态：已与用户逐项确认通过（4 轮澄清 + 方案取舍）
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-09-01-profile-schedule-calendar.md`

## 背景与问题

现有 `/alarms` 页（`webapp/alarms` 模块）是纯列表 + 新建表单，只能看自己创建的闹钟。用户诉求：

1. 在个人主页新增**日程功能，以月历形式展示**，每一天可互动（点选 → 添加闹钟）
2. 日历同时显示**当前用户的闹钟 + 群内所有人创建的群闹钟**（重复闹钟自动展开填充到日历）
3. 该页面**替代**旧闹钟页；新增闹钟表单放日历下方
4. 点闹钟弹悬浮窗：创建人/内容/触发规则；自己创建的可编辑可删除，别人的只读

## 已确认决策（逐项经用户确认）

| # | 决策 |
|---|------|
| D1 | 显示范围：我的全部未触发闹钟（私聊 + 我建的群）+ **所有人的群闹钟**（`is_private=0`）；我的有视觉标记；别人的只读。群闹钟内容对登录成员可见（触发时本就在群里公开） |
| D2 | 点日期格子空白 = 选中该天（高亮 + 滚到底部表单 + 预填「指定日期 = 该天」）；过去日期置灰不可选 |
| D3 | 新建/编辑表单带「提醒范围」开关：仅我（私聊）/ 群内公开；**编辑时允许私聊↔群互转** |
| D4 | 旧 `/alarms` 302 → `/profile/schedule`；`nav.js`「闹钟」改「日程」；profile 子导航（4 个页面）加「日程」；时间线侧边栏 `entries.json` 同步改；`webapp/alarms` 模块不搬家，只扩展 |
| D5 | 前端**手写月历网格**（不用开源日历组件）：本页本质是「可点选的闹钟面板」，格子内自定义条目是核心，库的价值部分用不上；复用打卡热力图的网格视觉语言 |
| D6 | 循环闹钟**服务端展开**：复用 `plugins/group_alarm/parser.py` 的 `_next_recurring_fire` 权威逻辑，前端零重复实现 |

## 非目标

- 不改数据库 schema（`group_alarms` 表已够用：`fire_at` = 下次触发时间，`recur_kind/a/b/c` 完整）
- 不改 bot 端任何代码（web 建的群闹钟与 QQ 建的走同一张表、同一个 `due()` 扫描器，触发行为天然一致）
- 不做周视图/议程视图/拖拽调期/ICS 导入（将来需要时再评估引入日历组件）
- 不做闹钟编辑的 bot 端 QQ 指令（web 编辑只改 web 可见的数据，bot 扫描器自动感知）

## ① API（全部在 `webapp/alarms`，登录门控由现有 login_guard 覆盖）

### 新增 `GET /api/me/calendar?month=YYYY-MM`

返回服务端展开好的按日分组条目：

```json
{
  "month": "2026-09",
  "days": {
    "2026-09-01": [
      {
        "id": 12, "time": "08:00", "content": "早起",
        "is_mine": true, "scope": "private",
        "is_recurring": true, "recur_desc": "每天",
        "creator_name": "小埃"
      }
    ]
  },
  "min_lead_minutes": 5
}
```

- 数据源两条查询（均为 `fired=0`）：
  - **我的**：`creator_user_id = ?`（含私聊 + 我建的群闹钟）
  - **别人的群闹钟**：`is_private = 0 AND creator_user_id != ?`（别人的私聊闹钟永不出服务器）
- 展开规则：
  - 单次闹钟：`fire_at` 落在所查月内 → 当天一条
  - 循环闹钟：**首步**以 `_next_recurring_fire(fire_at, now, kind, a, b, c)` 求真实下次触发（`fire_at` 落后于 now 时内部 catch-up 追平），**后续**以 `_next_recurring_fire(prev, prev, …)` 逐步推进到月末截止；只**向前**展开（`fire_at` 之前的历史不回溯——DB 不留已消耗的触发记录）。迭代加 10000 步保护上限（与 parser 既有守卫一致）
- 同一天内按 `time` 升序；`creator_name` 用 `core.onebot_client.resolve_display_name`（profile 模块已有先例）
- `month` 参数校验 `^\d{4}-(0[1-9]|1[0-2])$`，不合法 400

### 扩展 `POST /api/me/alarms`

`AlarmCreateIn` 加 `scope: str = "private"`（`"private" | "group"`，其他值 400）：

- `private`：现状行为，`db.alarm.add(..., group_id=None, is_private=True)`
- `group`：`db.alarm.add(..., group_id=DEFAULT_GROUP_ID, is_private=False)`（`core.context.DEFAULT_GROUP_ID`）

### 新增 `PUT /api/me/alarms/{id}`（编辑，仅创建者）

- Body 与 POST 相同（含 `scope`）
- 先查 `id + creator_user_id + fired=0`，查无 → 400「编号不存在、已触发或不是你创建的闹钟」
- 复用创建的整套校验（`_build_alarm_body` → `ga._parse_create_body` → fire/content/recur）
- `UPDATE group_alarms SET fire_at, content, is_private, group_id, is_recurring, recur_kind, recur_a, recur_b, recur_c`，编号不变
- 语义：编辑循环闹钟 = 重新指定规则，`fire_at` 从现在重算下次（等于删旧建新但保留编号）
- scope 互转：`private→group` 置 `group_id=DEFAULT_GROUP_ID, is_private=0`；`group→private` 置 `is_private=1`（group_id 列置 0，与 `add()` 私聊写入一致）

### 保留 `GET /api/me/alarms`（旧列表）

新页除日历外仍渲染完整的闹钟列表（跨月全局视图，日历一月一屏看不全），端点与返回结构不变。`DELETE /api/me/alarms/{id}` 原样保留（已天然支持群闹钟取消）。

## ② 前端 `/profile/schedule`（新静态页 schedule.html/js/css，手写月历）

### 页面结构（自上而下）

1. 站点导航 + profile 子导航（主页/打卡/日程/商店/设置）
2. 月历网格：周一起始，7 列 × 5–6 行，`‹ 2026年9月 ›` 切换 + 「今天」按钮；今天格子描边高亮
3. **日历下方**：新增/编辑闹钟表单
4. **表单下方**：全部闹钟列表（旧页列表搬运改造：按 `fire_at` 升序，显示时间/内容/循环规则/范围，我的可点入编辑；行点击 → 同一个闹钟详情悬浮窗）

### 日历格子

- 日期数字 + 闹钟条目（chip：`HH:MM 内容截断`），**我的闹钟强调色描边，别人的群闹钟中性色**
- 每格最多显示 3 条，超出折叠为「+N」chip
- 过去日期整格置灰（无 pointer 事件）
- **点 chip** → 闹钟详情悬浮窗；**点「+N」** → 当日全部闹钟列表悬浮窗（列表项可点 → 闹钟详情悬浮窗）；**点格子空白** → 选中该天：格子高亮 + 滚到底部表单 + 预填 `scheduleType="once_date"`、`date=该天`（时间留空待填）

### 闹钟详情悬浮窗（`<dialog>`，与站内 loginDialog/dayDialog 同模式）

- 显示：创建人昵称、内容全文、触发规则（`recur_desc` + 下次触发时间，或单次的绝对时间）、范围徽章（仅我/群内公开）
- `is_mine`：显示「编辑」（表单切编辑模式：标题变「编辑闹钟 #id」、按现有规则预填、保存走 PUT、「放弃」退回新增模式）+「取消闹钟」（DELETE，二次确认）
- 非本人：纯只读

### 新增/编辑表单（从 alarms.js 表单部分改造搬运，旧 alarms.html/js/css 删除）

- 8 种触发方式全保留：指定日期/相对时间/今天/每天/每 N 天/每周/每月/每年
- 新增「提醒范围」开关：仅我 / 群内公开（默认仅我）
- 提交成功 → 刷新日历与列表 + 重置表单；服务端 400（如提前量不足 5 分钟）→ 表单上方红字提示
- 编辑模式额外带「放弃编辑」按钮

### 闹钟列表（旧页列表搬运改造）

- 数据：`GET /api/me/alarms`（不变），仅自己的未触发闹钟
- 行内容：`fire_at`（前 16 字符）/ 内容 / 循环规则（`recur_desc`）/ 范围徽章；行点击 → 闹钟详情悬浮窗（编辑/取消入口与日历 chip 一致）

## ③ 路由与导航变更

| 文件 | 变更 |
|------|------|
| `webapp/alarms/app.py` | `GET /alarms` → `RedirectResponse("/profile/schedule", status_code=302)`；新增 `GET /profile/schedule` 返回 schedule.html；新增 PUT；POST 加 scope；删 GET 列表 |
| `core/web/static/nav.js` | `{ label: "闹钟", path: "/alarms" }` → `{ label: "日程", path: "/profile/schedule" }` |
| `webapp/static/{profile,checkin,shop,settings}.html` | profile 子导航加「日程」（打卡之后） |
| `webapp/timeline/entries.json` | 「闹钟」项 → 「日程」`/profile/schedule` |

## ④ 边界情况

- **并发**：编辑与 bot `advance()` 竞争同一行——SQLite WAL 行级串行，最后写赢；可接受（代码处 `# ponytail:` 注释标注，若出现丢更新再加 fire_at 前置条件比对）
- **循环闹钟 `fire_at` 在下月**：本月格子无条目（历史不回溯），悬浮窗/表单里规则描述仍完整
- **bot 停机期间 `fire_at` 落后于 now**：展开首步用真实 `now` 调 `_next_recurring_fire`（其内部 catch-up 循环会追平），与 bot 触发时的推进语义一致
- **私聊隐私**：别人的私聊闹钟在查询层即被排除，永不下发
- **时区**：全服务器本地时间（与 bot/web 现状一致）

## ⑤ 测试

新增 `test/test_alarm_calendar.py`（unittest 风格，进程内，conftest 已隔离数据路径）：

- 展开逻辑：每 N 日跨月 / 每周 / 每月（月末 31→30 钳位）/ 每年（2 月 29 → 28 钳位）/ 单次落位 / fire_at 在下月时本月为空 / 历史不回溯
- scope：POST group 写入 `group_id=DEFAULT_GROUP_ID, is_private=0`；PUT 互转两个字段正确翻转
- 权限：PUT/DELETE 非创建者被拒；日历响应中不含他人私聊闹钟
- 路由：`/alarms` 302；`/profile/schedule` 200
- 全量 `pytest` 回归通过

## ⑥ 文档与版本同步（同 commit）

- `CHANGELOG.md` 新 `[x.y.z]` 节 + `core/config.py::BOTERO_VERSION` minor bump
- `specs/web-gallery.md`：模块表/路由表/API 表/页面清单更新（新增 /profile/schedule、PUT、calendar API；/alarms 标注为重定向）
- `kb/QUICK_REFERENCE.md`：页面路径相关条目更新
- 不涉及：`kb/DATABASE.md`（无 schema 变更）、`kb/PLUGIN_CATALOG.md` 与 `plugins/menu/bot_menu_text.py`（bot 端指令无变化）、`kb/GAMEPLAY.md`
