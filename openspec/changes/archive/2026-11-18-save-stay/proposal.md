# 建卡页保存后留在编辑页（+ 补回缺失的 showToast）

## Why

两个问题合在一起让建卡流程很难走：

1. 新建卡保存成功后 `window.location.href = "/trpg"` 跳回列表，要应用年龄调整还得回列表点「编辑」再进来——这就是用户提出「能不能自动建卡」的真实摩擦点（多 3 次点击，不是缺卡号）。
2. 这个页面**从来没有定义过 `showToast`**（它只存在于 `trpg.js` / `trpg_levelup.js`），`trpg_coc.js` 里 12 处 `showToast(...)` 调用全是 `ReferenceError`：补本职技能、按规则填入、年龄调整成功/失败、撤销年龄调整、职业名不合法……的反馈全部静默丢失（其中一处还是用 `typeof` 守卫过的）。这也是「点了没反应」反复出现的原因之一。

## What Changes

- `save()`：成功后跳回**当前卡的编辑页** `/trpg/coc/<id>?saved=1`（新建时 `id` 来自响应，等于把卡号写进地址栏），不再跳列表。
- `init()`：`?saved=1` 时提示「已保存」/「已保存，现在可以应用年龄调整」（已有 `age_adjust` 时只说已保存），并用 `history.replaceState` 清掉参数，避免刷新重复提示。
- 页面补上 `<div id="toast">`，`trpg.css` 补 `.toast` 样式（底部居中胶囊、`.error` 变色、`[hidden]` 不占位），`trpg_coc.js` 定义 `showToast()`，让 12 处调用真正生效。
- 测试：新增 `test/test_trpg_coc_save_stay.js`（12 项）——保存跳转目标、`saved=1` 识别与清理、`showToast` 定义与真实执行（写入文字 / 显示 / 错误态）、`#toast` 容器与 `.toast` 样式存在。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：建卡页保存后的停留位置与操作反馈。

## Scope and Compatibility

- 新建与编辑两种保存都停留在编辑页；返回列表仍可用页签「车卡」。
- 不建卡、不写草稿、不产生空卡（对比「自动建卡」方案）。
- 版本 2.1.5。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 保存后留在编辑页 | `node test/test_trpg_coc_save_stay.js` | 跳转目标为 `/trpg/coc/<id>?saved=1`，源码里不再有保存后跳 `/trpg` |
| AC02 提示与清理 | 同上 | 识别 `saved=1`、含「现在可以应用年龄调整」、`history.replaceState` 清理参数 |
| AC03 showToast 可用 | 同上 | 本页定义 `showToast`；真实执行后 `textContent` 写入、`hidden=false`、错误态带 `error` 类 |
| AC04 页面承载 | 同上 | `trpg_coc.html` 有 `#toast`，`trpg.css` 有 `.toast` 与 `.toast[hidden]` |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.1.5]` 与 `BOTERO_VERSION` 一致 |
