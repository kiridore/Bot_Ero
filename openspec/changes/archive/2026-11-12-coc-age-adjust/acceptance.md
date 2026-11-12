# 年龄调整 — 验收记录

实施分支：`master`；版本 1.83.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 年龄段表 | `python -m pytest test/test_trpg_coc_age.py -q` → 25 passed。`TestAgeBands::test_band_boundaries` 覆盖 15/19/20/39/40/49/50/60/70/80/90 的体能项、额度、APP、EDU 检定次数、EDU 定值与幸运取高 | 通过 |
| AC02 MOV 公式 | `test_mov_formula`：0/15/39/40/49/50/80/89/90/99 岁 → 0/0/0/1/1/2/5/5/6/6；`TestFinalize::test_mov_uses_new_formula` 校验 finalize 口径 | 通过 |
| AC03 应用 | `check_trpg_coc_api.py`：45 岁卡 `POST .../age-adjust` 体能 −3/−2/0 → 力量 60→57、体质 55→53、外貌 60→55（−5）、教育只增不减、`age_adjust.band=40-49`、HP 随体质重算 10→9、MOV 9→8 | 通过 |
| AC04 校验 | 同上：合计不符（−2）→ 400「体能合计应扣 5 点」；正数分配 → 400「0 或负数」；改年龄 → 400「年龄已从 45 改为 50」；手改力量 → 400「请勿手工修改力量」；重复应用 → 400「已经应用过」 | 通过 |
| AC05 撤销 | 同上：`DELETE .../age-adjust` 后力量/体质/外貌/教育回到 60/55/60/45、记录消失；重复撤销 400；`skip` 写入 `kind: skipped` 且后续整卡保存不拦 | 通过 |
| AC06 旧卡兼容 | 同上：无 `age_adjust` 的卡（新建 + 改名保存）返回 200 且 `age_adjust` 为 `null`；`test_missing_record_is_allowed` 校验层同样放行 | 通过 |
| AC07 页面 | `node test/test_trpg_coc_age_dom.js` → 22 项全过：年龄段提示、体能格数量（3/2/0）、合计不符禁用按钮、正数拦截、已应用明细与只读、年龄改动提示、15–19 幸运取高（45/70 取 70）、skipped 可应用 | 通过 |
| AC08 全量回归 | `python -m pytest -q` → **884 passed**（5:11） | 通过 |
| AC09 文档与归档 | `openspec validate 2026-11-12-coc-age-adjust --strict` valid；`kb/GAMEPLAY.md` 新增「跑团（COC 7th）建卡年龄调整」；`CHANGELOG [1.83.0]` 与 `BOTERO_VERSION = "1.83.0"` 一致；归档与实现同一 commit | 通过 |

## 实现中的裁定与发现的坑

- **年龄段表单一来源**：`core/trpg/coc.py::AGE_BANDS`，网页通过 `/api/trpg/coc/options` 的 `age_bands` 取，前端不再复制一份（旧 `agePenalty` 查表已删除）。
- **`age_band` 上限收紧到 99**：最初表里 90+ 段写 `max: 999`，导致 `age_adjustment(100)` 仍返回某段；改为先判 `AGE_MIN..AGE_MAX`。
- **撤销必须同时还原教育**：`before` 只存体能项与外貌，教育在 `edu.before` 里；`undo_age_adjust` 单独补了 `edu_score`，否则撤销后教育停在加过的数值（测试 `test_undo_restores` 抓到）。
- **防重复应用**：接口拒绝在已有 `kind: applied` 记录时再次 apply/skip，必须先撤销——否则属性会被扣两遍。
- **整卡保存不清记录**：`PUT` 一律沿用卡上 `age_adjust`；无记录时从 payload 里 pop，避免写入 `null`。
- **已应用属性只读**：`lockAgeAttrs` 按记录里的年龄段锁定对应输入框；服务端 `age_adjust_problems` 兜底（`before + delta == 当前值`），绕过页面直接调接口改属性会被 400 拦下。
- **前端年龄段显示用记录里的 band**：年龄改到别的段（如 40-49 → 15-19）时，明细仍按记录取体能项，不会出现 `体型 undefined`。
- **EDU 成长检定服务器掷**：`POST` 时服务端 `random.randint`，刷新页面不能重掷；撤销后重新应用会重掷（团内无作弊动机，已在设计文档标注）。
- **未做**：15 岁以下的小学生转换规则、游戏内逐十年老化指令、`/跑团 角色 查看` 的年龄调整摘要（查看页有，QQ 端没有）。
