# 观察者发言改为「观战席」样式

## Why

观察者在跑团里是观战席上的人，不在舞台上。但现在记录页里观察者的发言和玩家一模一样：左侧头像、实底气泡、同样字号，只有名字后面一个灰徽标，翻记录时很难一眼区分「谁在演、谁在看」。

## What Changes

- `trpg_record.js` 新增 `renderObserver(m)`：`role === "ob"` 的用户消息走观战席分支——不渲染头像与气泡，改成一条灰色细线：`👁 群昵称 [暗骰] 21:34 · 正文`，长文在剩余宽度内换行（悬挂缩进）。
- 观察者的图片保留 `trpg-img` 类（灯箱仍可点开），追加 `trpg-ob-img` 缩小到最大 8×6rem。
- 观察者的暗骰消息显示虚线「暗骰」小标签；场外发言（整句括号）仍受「隐藏场外发言」开关控制。
- 自己看自己（观察者本人）时细条右对齐，保持既有「自己消息在右」的语义。
- CSS 新增 `.trpg-msg.trpg-ob` 系列（缩进 1.75rem、`--ink-soft`、0.82rem、0.88 不透明度）。
- DM 不受影响，仍是正常气泡。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：观察者消息的呈现形态。

## Scope and Compatibility

- 纯前端；`messages.jsonl`、接口与数据不变。
- 观察者仍出现在「参团角色卡」列表（若绑定了角色卡），仍可点开角色卡。
- 无数据库变更、无新增依赖；版本 1.90.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 细条形态 | `node test/test_trpg_records_dom.js` | 观察者消息带 `trpg-ob`，没有 `trpg-bubble`、没有 `trpg-avatar` |
| AC02 组成 | 同上 | 依次有 `trpg-ob-mark`（眼睛图标）、`trpg-ob-who`（群昵称）、`trpg-ob-time`、`trpg-ob-text`（正文完整） |
| AC03 图片 | 同上 | 观察者图片同时带 `trpg-img` 与 `trpg-ob-img`，灯箱仍可打开 |
| AC04 暗骰与场外 | 同上 | 观察者暗骰显示 `trpg-ob-tag`；整句括号的观察者发言仍带 `is-ooc` |
| AC05 DM 不变 | 同上 | DM 消息仍有 `trpg-bubble` |
| AC06 样式存在 | 同上 | CSS 含 `.trpg-msg.trpg-ob` 与 `.trpg-img.trpg-ob-img` |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.90.0]` 与 `BOTERO_VERSION` 一致 |
