# 跑团记录：隐藏场外发言的开关

## Why

复盘跑团记录时，玩家常把与剧情无关的话整句包在括号里（`（我去倒杯水）`、`(等下我查下规则)`）。这些话混在气泡流里干扰阅读，但目前没有任何过滤手段。

## What Changes

- `webapp/static/trpg_record.js` 新增 `isOoc(message)`：整条消息都是文本、且去掉首尾空白后被半角 `( )` 或全角 `（ ）` 完全包裹、括号内非空 → 视为场外发言；带图片/@ 等非文本段的消息一律不算。
- 场外消息渲染时加 `is-ooc` 类。
- 详情页头部新增「隐藏场外发言」勾选框：勾上给消息容器加 `hide-ooc`，CSS 隐藏 `.is-ooc`；状态存 `localStorage`（`botero_trpg_hide_ooc`），刷新后保持。切换纯客户端，不重新请求接口。
- 默认不隐藏（信息不默认消失）。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：记录详情页的展示过滤。

## Scope and Compatibility

- 只影响详情页渲染；`messages.jsonl`、`meta.json`、`record.md`、接口返回都不变，暗骰开关行为不变。
- `localStorage` 不可用（隐私模式）时退化为仅本次生效，不报错。
- 无数据库变更、无新增依赖；版本 1.85.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 识别规则 | `node test/test_trpg_records_dom.js` | 全角/半角整句包裹为场外；括号只在开头或只在结尾、空括号、带图片的消息都不算 |
| AC02 渲染标记 | 同上 | 场外消息带 `is-ooc` 类，普通消息不带 |
| AC03 开关 | 同上 | 勾选后消息容器有 `hide-ooc`、取消后移除；状态写入 `localStorage` |
| AC04 HTML/CSS | 同上 | `trpg_record.html` 含 `oocToggle` 与「隐藏场外发言」；CSS 有 `.trpg-thread.hide-ooc .trpg-msg.is-ooc` 规则 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.85.0]` 与 `BOTERO_VERSION` 一致 |
