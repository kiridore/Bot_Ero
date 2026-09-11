# 单群多活动并行设计

日期：2026-09-09 · 状态：已确认（用户裁定）

## 目标

解除「一个群同时只能有一个 open/running 活动」限制，允许并行多个；参加、提交、开始、结束、状态查询均可指定具体活动。

## 决策表

| # | 决策 |
|---|------|
| D1 | 指令语法：`/活动 加入\|退出\|开始\|状态\|结束 [编号]`（编号 = 全局活动 id，公告已带 `#123`）；`/提交 [活动id]` 既有语义不变 |
| D2 | 省略编号的解析：唯一候选自动选中；多个候选列出编号并要求指定；零候选返回该命令空态文案（与 `/提交` 多活动提示风格一致） |
| D3 | 创建不再校验「本群已有进行中的活动」（bot + web 两处），并发数量不设上限（YAGNI） |
| D4 | `/活动 状态` 无编号：唯一候选直接显示既有详情体；多个候选列出本群全部进行中活动摘要（编号/类型/标题/报名数或完成进度）+ 提示「查看详情：/活动 状态 <编号>」；带编号 = 既有详情体 |
| D5 | 数据层新增 `get_active_activities_for_group(gid)`；保留 `get_active_activity(gid)`（无参取最新，测试与兼容用），生产路径不再使用 |
| D6 | 心跳扫描、`/提交` 归属解析、web 详情/加入/提交/结束/归档均已按活动 id 工作，零改动 |

## 改动点

- `core/db/activity.py`：新增 `get_active_activities_for_group`
- `plugins/activity/__init__.py`：`_pick_from(candidates, arg, cmd)` 选择助手；join/leave/start/status/end 五个 handler 改为「候选集 + 可选编号」；`_handle` 分发透传 `args[1]`；usage 文案加 `[编号]`；创建 guard 移除
- `plugins/menu/bot_menu_text.py`、`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`：指令文本同步
- `webapp/activities/app.py`：移除创建 guard
- 测试：bot 并发双活动用例（创建 2 个 / 指定加入 / 指定开始 / 状态列表 / 指定结束 / 指定提交）；web API 并发创建 200

## 边界

- 同一用户在多个活动中可各自持有成员态与提交（互不影响）
- 退出/开始时若同时存在多个候选且用户未给编号 → 报错列编号，不做猜测
- 权限校验（创建人/超管）在选中活动之后进行，语义不变
