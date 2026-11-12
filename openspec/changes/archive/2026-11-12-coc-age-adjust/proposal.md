# COC 7th 建卡年龄调整

## Why

建卡工具目前只把年龄用于 MOV 减值（`age_mov_penalty`），规则书要求的其余年龄效果全缺：

- 40 岁起 STR/CON/DEX **合计**减 5/10/20/40/80、APP 减 5/10/15/20/25 完全不应用——70 岁角色可以有 20 岁的力量、体质与外貌。
- EDU 成长检定一次都不掷（20–39 岁 1 次、40 岁起 2/3/4/4 次）。
- 15–19 岁的「STR 与 SIZ 合计 −5、EDU −5、幸运掷两次取高」不支持。
- 年龄字段服务端零校验（0 或 999 都能存）。
- MOV 查表停在 80 岁（−5），规则是「之后每十年 −1」，90 岁应为 −6。

权威依据：`docs/COC7th守密人核心规则书.pdf` 创建调查员流程（15-19/20-39/40-49/…/80-89 的调整表与 EDU 成长检定口径）与老化规则（累加，结果与建卡表一致）。

## What Changes

- `core/trpg/coc.py` 新增 `age_adjustment(age)` 年龄段表与 `apply_age_adjust()`：按段返回体能合计额度、体能项（40 岁以上 STR/CON/DEX；15–19 为 STR/SIZ）、APP 额度、EDU 成长检定次数（15–19 另有 EDU 定值 −5）、是否幸运取高、MOV 减值。
- MOV 改为公式 `max(0, age // 10 - 3)`，覆盖 90 岁以上，与人物卡公式 `INT(age/10)-3` 一致。
- 新增卡片字段 `age_adjust`（`kind: applied|skipped`），记录本次调整的年龄段、体能分配、APP、EDU 成长检定明细、调整前数值与应用时间。
- 新增两个接口：`POST /api/me/characters/{id}/age-adjust`（`action: apply|skip`，应用时**服务器**掷 EDU 成长检定）与 `DELETE /api/me/characters/{id}/age-adjust`（撤销，按 `before` 还原）。
- 建卡页新增「年龄调整」区块：显示按年龄应做的调整，**体能合计扣减由玩家自己填**（三项之和必须等于额度，负数），应用后属性只读并显示明细，可撤销；15–19 岁显示「幸运掷两次取高」按钮。
- `validate()` 新增：`age` 非 0 时必须是 15–99 的整数；`age_adjust.kind == applied` 时年龄必须与记录一致、体能分配必须等于额度、调整后属性必须等于 `before + delta`（禁止事后手改被调整的属性）。
- 未做年龄调整的既有卡：`age_adjust` 缺失视为「未处理」，属性原样不动、保存不拦，编辑页显示一次性提示与「应用 / 不再提示」；不写迁移脚本。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：年龄调整的数据、接口、页面与校验。

## Scope and Compatibility

- **既有卡零迁移**：`age_adjust` 缺失 = 未处理，`kind` 缺省不校验，属性与派生值与上线前完全一致（唯一例外：90 岁以上 MOV 由 −5 变 −6，符合规则）。
- 应用年龄调整会连带改变 HP（体质）、伤害加值与体格（力量）、闪避与 MOV（敏捷）、职业点预算与母语（教育）——这些都由现有 `finalize()` 自动重算，不需要额外代码。
- 撤销采用「删除 `age_adjust` 并按 `before` 还原」，重新应用会重掷 EDU 成长检定；团内无作弊动机，接受这一简化（代码留 `shortcut:` 注释）。
- 不做：15 岁以下的小学生转换规则、游戏内逐十年老化的指令（仍由玩家改年龄后重新应用）、`/跑团 角色 查看` 增加年龄调整摘要。
- 无数据库变更、无新增依赖；版本 1.83.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 年龄段表 | `python -m pytest test/test_trpg_coc_age.py -q` | 15/19/20/39/40/49/50/60/70/80/89 各段返回的体能额度、体能项、APP、EDU 检定次数、幸运取高与规则表一致 |
| AC02 MOV 公式 | 同上 | 39 岁 0、40 岁 1、49 岁 1、50 岁 2、80 岁 5、90 岁 6、99 岁 6；未填年龄（0）为 0 |
| AC03 应用 | `python test/scripts/check_trpg_coc_api.py` | `POST .../age-adjust` 按传入分配扣属性、按服务器掷骰结果加 EDU、写入 `age_adjust`；返回的 `hp/db/mov` 随之变化 |
| AC04 校验 | 同上 | 体能三项之和 ≠ 额度、正数分配、年龄不一致、事后手改被调整属性 → 400 且含中文原因 |
| AC05 撤销 | 同上 | `DELETE .../age-adjust` 后属性等于 `before`、`age_adjust` 消失、`kind=skipped` 时同样可应用 |
| AC06 旧卡兼容 | 同上 | 不含 `age_adjust` 的卡可正常保存与读取，属性不被改动；`kind=skipped` 不拦保存 |
| AC07 页面 | `node test/test_trpg_coc_age_dom.js` | 年龄段提示文案、体能输入框数量（3 或 2）、合计不符时按钮禁用、已应用时属性只读、15–19 显示幸运取高按钮 |
| AC08 全量回归 | `python -m pytest -q` | 全绿 |
| AC09 文档与归档 | `openspec validate 2026-11-12-coc-age-adjust --strict`；归档与实现同一 commit | `CHANGELOG [1.83.0]` 与 `BOTERO_VERSION` 一致；`kb/GAMEPLAY.md` 记录年龄调整表 |
