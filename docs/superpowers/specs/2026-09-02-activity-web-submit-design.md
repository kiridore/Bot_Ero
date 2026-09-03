# 活动详情页个人提交与网页提交 — 设计文档

- 日期：2026-09-02
- 状态：已与用户逐项确认通过（设计分节一次通过）
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-09-02-activity-web-submit.md`

## 背景与问题

活动详情页（`/activities/{id}`）现状：进行中只能看人员状态列表，**自己的已提交内容不可见**；作品区仅在 finished 后展示**所有人**的作品。提交入口只有 QQ 私聊 `/提交`。

诉求：详情页显示**自己的**提交（不含其他人）；新增网页端提交作品界面。

## 已确认决策

| # | 决策 |
|---|------|
| D1 | 详情页**新增**「我的提交」区块（进行中即可见自己的文字+图片+提交时间，可更新）；finished 后仍展示全部作品（归档公开不变） |
| D2 | 隐私剥离：`GET /api/activities/{id}` 在活动**非 finished** 时，非本人成员的 `content/images/submitted_at` 置空（现状是 API 全量下发、页面未渲染——数据层落实「不包含其他人」） |
| D3 | 网页提交语义与 bot `/提交` 逐条对齐：member 存在、活动 running、非 left/missed/skipped、relay 须轮到你；done = 更新（覆盖式：content/images 整体替换，与 bot `update_member(content or None, ...)` 语义一致） |
| D4 | relay 推进由 `activity_timer` 心跳补发（webapp 无法发 QQ 消息）：当前棒 `received_at` 为空且上一棒 done → 补「完成接力」公告 + `_relay_advance`；≤60s 延迟；bot 端提交即时推进不进此分支（天然幂等） |
| D5 | match 网页提交不发群公告（无消息通道，页面 toast 反馈）；进度公告/截止收尾照旧 |
| D6 | 图片复用打卡限制（`CHECKIN_MAX_IMAGES=9` / `CHECKIN_MAX_BYTES=10MB` / JPG·PNG·WebP·GIF），存 `ACTIVITY_ROOT/<id>/imgs/<seq>-<n>.<ext>`（与 bot 同名规则），先全部存盘成功再写库 |

## 非目标

- 不改 `activities`/`activity_members` 表结构
- 不做网页报名/退出（维持 QQ 指令）
- 不做网页端消息通知（timer 已覆盖 relay 推进；match 公告舍弃）

## ① API（`webapp/activities/app.py`）

### 新增 `GET /api/activities/{id}/me`（登录必需）

```json
{
  "member": {"status": "done", "seq": 2, "content": "…", "submitted_at": "…",
              "images": ["/archive/3/media/2-1.jpg"]} | null,
  "can_submit": false,
  "block_reason": "not_my_turn" | null
}
```

`block_reason` 枚举与判定（顺序即优先级）：`not_member`（非成员，member=null）→ `not_started`（open/cancelled）→ `finished` → `missed`（missed **或 skipped**，提示「已截止或被跳过」）→ `left` → `not_my_turn`（仅 relay：非当前棒 pending）。`can_submit = block_reason == null`。当前棒判定在 webapp 内重实现（取成员按 seq 排序首个 pending，5 行；webapp 不 import plugins）。

### 新增 `POST /api/activities/{id}/submit`（multipart，照打卡页 async 先例）

- 字段：`content`（文本，可选）+ `files`（多图，可选）；校验链复用 me 的判定（can_submit 为假 → 409 + 原因文案）
- 文字与图片至少一项；图片走 D6 限制；**先全部存盘成功再写库**（任一失败 400 整体不生效，与 bot「下载失败重试」语义一致）
- 成功：`update_member(status="done", content=content or None, images=json or None, submitted_at=now)`；返回 `{"ok": true, "updated": bool}`（此前 status=done 则 updated=true）
- 命名 `f"{seq}-{n}{ext}"`（n 从 1 递增；更新覆盖 images 字段，旧文件留磁盘——与 bot 一致）

### 修改 `GET /api/activities/{id}`（D2 剥离）

路由加 `get_current_user_id` 依赖；`status != "finished"` 时非本人成员的 `content=None, images=[], submitted_at=None`；本人与 finished 全量。管理页（owner 用）不消费 content/images，已核实无影响。

## ② bot 侧：`activity_timer` 补推进（`plugins/activity/__init__.py`，~15 行）

提取模块级函数：

```python
def _relay_catchup(api, db, act, members) -> bool:
    """网页提交补推进：当前棒 pending 且 received_at 空 且 上一棒 done → 补公告并推进。"""
```

`_scan` 的 relay 分支：先调 `_relay_catchup`，返回 True 则刷新 members（推进/收尾已发生，本 tick 跳过超时判定）；False 走原超时逻辑（零改动）。活动开始的 seq1 由 `_start_activity → _relay_advance` 置 received_at，`cur.received_at 空 && 无上一棒 done` 是不可能态，函数自然返回 False，无需特判。

## ③ 前端（`activities_detail.js` + html 内嵌样式）

- `loadDetail` 并行 `Promise.all` 拉详情 + me API
- 参加人员区块下方新增「我的提交」区块（member 非空才渲染）：文字 + 图片（复用 `.work-content/.work-img` 既有样式）+ 提交时间 + 状态徽章
- 其下「提交作品」表单：`can_submit` → textarea + 多图选择 + 提交按钮（FormData POST，成功 toast + 重拉两个 API）；`block_reason` 非空 → 单行原因提示替代表单；`not_member` → 两块整块隐藏
- 原因文案映射：not_my_turn「还未轮到你提交」/ missed「已截止或被跳过，无法提交」/ left「你已退出活动」/ not_started「活动未开始」/ finished「活动已结束」

## ④ 边界情况

- 网页与 bot 同时提交同一成员：SQLite 行级最后写赢（`# ponytail:` 注释标注，同闹钟编辑策略）
- 「网页提交瞬间被 timer 判超时」：不可能——超时判定对象是 pending，提交瞬间已置 done
- match 截止后提交：deadline 收尾已置 missed → `missed` 拒绝
- relay 链尾经网页提交：`_relay_catchup → _relay_advance` 返回 False → `_finish_activity` 归档，与 bot 一致

## ⑤ 测试

- `check_activities_api.py` 扩展：me 状态矩阵（非成员/not_started/finished/missed/left/not_my_turn/可提交）、提交成功、更新覆盖（图片重传）、权限与状态拒绝、D2 剥离（进行中他人 content 空 + 本人保留 + finished 全量）
- 新增 `test/test_activity_relay_catchup.py`：进程内直调 `_relay_catchup`（stub api 记录公告）：上一棒 done 未推进 → 公告+received_at 置位；无 done 前驱/已激活 → False 不动
- 新增 `test/test_activities_detail_render.js`：node DOM——我的提交区块渲染（文字+图）、can_submit 表单态、not_my_turn 原因态、not_member 隐藏
- 全量 `pytest` 回归

## ⑥ 文档与版本（同 commit）

- CHANGELOG `[1.34.0]` minor + `BOTERO_VERSION` bump
- `specs/web-gallery.md`：API 表新增 me/submit、detail 剥离说明
- `kb/PLUGIN_CATALOG.md`：`activity_timer` 职责行补「网页接力提交补推进」
- `kb/DATABASE.md` 不动（无 schema 变更）
