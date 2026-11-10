# COC 建卡页补齐武器表

## Why

1.66.0 引入 COC 建卡工具时，后端 `weapons` 字段、接口与 xlsx 的武器区数据都在，但**建卡页没有武器表界面**，玩家无法录入武器——功能缺口由所有者清点「跑团系统还有什么没补齐」时发现并点名先补。

## What Changes

- COC 建卡页新增「武器」区块：表格可增删行，字段为武器名称、成功率、伤害、射程、次数、弹药、故障值、贯穿（对齐 xlsx 武器区）。
- 新建调查员卡默认带一行「徒手格斗 25% 1D3+DB」。
- 保存与编辑回填：`weapons` 数组随卡片保存，名称留空的行不提交。
- 无后端字段变更（`weapons: list[dict]` 已在 1.66.0 落地），无校验规则新增。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：建卡页面要求补充武器表录入。

## Scope and Compatibility

- 不新增武器数据表与自动补全（武器名、伤害由玩家填写）。
- 护甲值、同伴、古籍咒文等 xlsx 其余区块仍不在本次范围。
- 无数据库变更、无新增依赖；旧卡没有 `weapons` 字段时武器区为空。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 页面录入 | `node --check webapp/static/trpg_coc.js`；DOM 层人工验收 | 武器区块可添加/删除行，八个字段可编辑，新建卡默认带「徒手格斗」一行 |
| AC02 保存与回填 | `python test/scripts/check_trpg_coc_api.py` | 带两把武器的卡保存后返回同样两把；更新为一把「短棍」后返回只有「短棍」 |
| AC03 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG` 顶部 `[1.68.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
| AC04 真实环境冒烟 | 部署机手工 | 网页建 COC 卡：添加两把武器并保存，重新打开编辑能看到两行并可删改 |
