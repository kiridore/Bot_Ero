# COC 7th 调查员建卡工具与角色卡规则字段

## Why

所有者指令（2026-11-11）：「角色卡也需要包含规则，之前的角色卡是只适配 DND5E 规则，还没有做 COC7th 的角色卡，参考 docs/COC七版人物卡v1.6.1.xlsx、COC7th 调查员/守密人核心规则书设计一版，仿照已经有的 DND5E 的页面逻辑。」并明确「我要做的是一个网页版的建卡工具，不是角色卡录入器」。

现状：角色卡只有 DND 5E 结构（`core/trpg/character.py::finalize`），没有规则字段；网页 `/trpg` 只有 DND 车卡表单；`.ra` 只接受数值，拿不到 COC 技能值。

## What Changes

- **卡片带规则字段**：`rules` 取 `dnd5e` / `coc7th`，缺省 `dnd5e`（旧卡不变）。
- **COC 建卡工具**：新增 `/trpg/coc`（新建）与 `/trpg/coc/<编号>`（编辑）。按 xlsx 口径：8 属性（3d6×5 / (2d6+6)×5 掷骰或手填）、年龄与 MOV 减值、职业模板（信誉区间、技能点公式、本职技能）、技能表（基础/成长/职业/兴趣 → 成功率，上限 99）、信用评级、武器、资产、背景六项、克苏鲁神话、笔记。
- **派生值**：HP=(体质+体型)//10、MP=意志//5、SAN=意志、MOV=基础值（力量/敏捷与体型比较）− 年龄减值、伤害加值与体格按 STR+SIZ 查表、闪避=敏捷//2；职业点预算按职业公式（教育×4 等），兴趣点 = 智力×2。
- **校验**：属性 1–99、职业点/兴趣点不得超预算、信用评级在职业区间内、必须选择职业、技能成功率 0–99；超限返回 400 与中文原因。
- **数据表**：技能基础值与 114 个职业模板从 xlsx 提取到 `core/trpg/coc_data.py`；`core/trpg/coc.py` 负责 finalize/validate/技能查询/人物简表。
- **规则一致性**：`/跑团 准备` 时若当前角色卡规则与本团规则不符，拒绝准备并提示切换角色卡或让 DM 改规则。
- **COC 检定读卡**：`.ra 侦查` 从当前 COC 卡取成功率（含「侦查/侦察」等别名），`.ra 60` 仍按数值；`/跑团 角色 查看` 按卡片规则输出 DND/COC 两种简表。
- **网页入口**：`/trpg` 列表提供「新建 DND 5E 卡」「新建 COC 7th 卡」两个按钮，COC 卡编辑跳转建卡页，列表按规则显示摘要。

## Capabilities

### New Capabilities

- `coc-character-sheet`：COC 7th 建卡数据（技能基础值、职业模板）、派生值与校验口径、建卡页面与接口、技能查询与人物简表。

### Modified Capabilities

- `trpg-party-setup`：`/跑团 准备` 增加「角色卡规则必须等于本团规则」校验。

## Scope and Compatibility

- 年龄只影响 MOV（与 xlsx 建卡工具一致）；年龄对属性本身的增减由玩家自行处理，不做自动扣减。
- 不做职业点数自动分配、不做建卡向导分步、不做随机姓名/背景生成。
- COC 检定不与 DND 属性互通；两套卡片各自独立，互不转换。
- 旧卡无 `rules` 字段按 DND 5E 处理，不改写历史文件。
- 无数据库变更；无新增第三方依赖（xlsx 已在仓库内作为数据来源，提取结果入库）。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 派生值 | `python -m pytest test/test_trpg_coc.py -q` | HP/MP/SAN/MOV/DB/体格/闪避按原版口径计算；MOV 含年龄减值；STR+SIZ 落在 64/84/124/164/204/205 边界时 DB 与体格正确 |
| AC02 预算与校验 | 同上专项 | 职业点/兴趣点按职业公式与智力×2 计算；超预算、信用评级越界、未选职业、技能越界各自报错 |
| AC03 技能查询 | 同上专项 | `.ra` 用的 `skill_value` 支持精确名、类别前缀与「侦查→侦察」别名；人物简表只列高于基础值的技能 |
| AC04 建卡接口 | `python test/scripts/check_trpg_coc_api.py` | 选项接口返回职业与技能基础值；建卡与更新返回派生值；超预算/信用越界/未选职业返回 400；规则字段写入并保留 |
| AC05 规则一致性 | `python -m pytest test/test_trpg_session.py -q` | 角色卡规则与本团规则不符时 `/跑团 准备` 被拒且不入名单；一致时正常准备 |
| AC06 骰子读卡 | `python -m pytest test/test_trpg.py -q` | `.ra 侦查` 输出卡上成功率（如 45）；卡上没有的技能名给出提示 |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict`；`openspec validate trpg-party-setup --strict` | 全量回归绿；`CHANGELOG` 顶部 `[1.66.0]` 与 `BOTERO_VERSION` 一致；插件目录已同步；归档与实现同一 commit |
| AC08 真实环境冒烟 | 部署机手工 | 网页建一张 COC 卡并保存 → `/跑团 角色 查看` 输出调查员简表 → DM 设规则 coc7th → 玩家准备 → `.ra 侦查` 用卡上技能值检定 |
