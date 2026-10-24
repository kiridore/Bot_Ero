# 谁是卧底投票结算修复

## Why

所有者报告出局玩家不是得票最高者。基于部署版本91e918c复现：2/2/0/0时现行平票分支真实淘汰零票者，存活状态、历史及QQ显示一致；另复现1号被前缀匹配到10号、最后两票并发导致同轮重复结算。所有者授权修复。

## What Changes

- 唯一最高票正常淘汰；最高票并列时仅在并列者中随机选择，不选择零票或较低票玩家。
- 投票编号按完整代号匹配，保留数字、号后缀及圈号输入。
- 投票阶段/重复校验、选目标、写入及完成判断在现有game_lock内进行；只用存活玩家是否全部投票判断完成，不用总票数替代。只有一个事件获得本轮完成信号，锁不跨消息发送。
- 不新增指令，不改赔率/称号/胜负条件；同步玩法规则与回归测试。

## Capabilities

### New Capabilities
- `spy-vote-settlement`：最高票淘汰、准确编号及并发只结算一次。

### Modified Capabilities
- 无（运行分支未包含对应OpenSpec能力）。

## Scope

从master部署版本建立fix/spy-vote-settlement，不混入dev社区功能，不自动合并master/dev、不推送。版本按运行基线修复号1.50.1。真实QQ联调未授权，不宣称上线。

## Acceptance Criteria

| 编号 | 验证 | 标准 |
|---|---|---|
| AC01 | pytest test/test_who_is_spy_votes.py -k highest | 四人81种合法投票组合，出局者均属于最高票集合；实际alive/history/QQ输出一致 |
| AC02 | pytest test/test_who_is_spy_votes.py -k number | 10号排在1号前时输入1仍投1号；数字/圈号/号后缀、无效编号、自投、重复、已出局校验保留 |
| AC03 | pytest test/test_who_is_spy_votes.py -k concurrent | 固定最后两票线程交错，真实处理函数仅追加一次历史、只进入下一轮一次；同账号并发仅录入一次 |
| AC04 | pytest test/test_who_is_spy_votes.py -k completion | 已退出者的旧票不让尚未全部提交的存活玩家提前结束；发送过程中不持全局游戏锁；下一轮可正常投票 |
| AC05 | python -m pytest；openspec validate spy-vote-settlement --strict | 全量通过；文档及1.50.1一致；先临时副本归档验证，再真实归档与实现同一提交 |
