# 点数超预算的卡：可以保存，但不能当作当前角色

## Why

职业点/兴趣点超预算现在直接把保存打成 400，玩家在长卡（几十项技能、可选池）里微调点数时，只要一时超支就连临时状态都存不下来。反过来，一张「超支但已存下」的卡如果还能被设为当前角色，群里 `.ra`、`/跑团 准备` 就会拿着一张违规卡开团。

## What Changes

- `core/trpg/coc.py`：把「职业点超预算 / 兴趣点超预算 / 未选职业却加职业点」从 `validate()`（拦保存）拆到新的 `budget_problems()` 与 `legality_problems()`（拦使用）。保存仍然拦结构性问题（属性范围、信用评级区间、非本职技能加点、可选池越界、武器/物品/资产/年龄一致性）。
- 保存接口：超支卡返回 200，响应里新增 `illegal`（原因列表）。
- `POST /api/me/characters/{id}/activate`：`illegal` 非空 → 400「这张卡还不能设为当前角色：…」。
- QQ 端 `/跑团 角色 切换`：同样拒绝并列出原因；`/跑团 角色 列表` 给不合法卡标「⚠️不可用（点数超预算）」。
- `/跑团 准备`：当前卡不合法 → 拒绝并说明；开录校验新增「角色卡点数超预算」一项（@ 出具体是谁）。
- 页面：建卡页保存后若有 `illegal` 弹窗提醒（仍跳回列表）；角色卡列表的「设为当前」按钮对不合法卡禁用并给出 tooltip。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：卡合法性的判定与保存/使用边界。

## Scope and Compatibility

- 只调整「超预算」这一类；其它校验的拦截时机不变。
- DND 卡不受影响（`legality_problems` 对非 COC 卡返回空）。
- 已设为当前角色、之后被编辑成不合法：不会自动取消当前卡，但 `/跑团 准备` 与开录校验会拦住。
- 版本 2.1.2。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 保存不拦 | `python -m pytest test/test_trpg_coc_legality.py -q` | 职业点/兴趣点超预算与「无职业加点」都不出现在 `validate()` 里 |
| AC02 使用要拦 | 同上 | `legality_problems()` 分别报出三种原因；DND 卡返回空 |
| AC03 接口行为 | `python test/scripts/check_trpg_coc_api.py` | 超支卡 POST 200 且 `illegal` 含原因；`activate` 400；改回预算内后 `illegal` 为空且 `activate` 200 |
| AC04 QQ 切换 | `python -m pytest test/test_trpg_char.py -q -k switch` | 超支卡切换被拒，`set_current` 未被调用 |
| AC05 准备与开录 | `python -m pytest test/test_trpg_session.py -q -k prepare` | 超支卡 `/跑团 准备` 被拒，`prepared` 仍为空 |
| AC06 页面 | `node test/test_trpg_coc_bind_runtime.js` 等 COC 用例全过 | 建卡页脚本语法与初始化正常 |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.1.2]` 与 `BOTERO_VERSION` 一致 |
