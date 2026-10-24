# 验收记录

## 基线与范围

基于部署提交91e918c6566ee4，独立分支fix/spy-vote-settlement；版本1.50.1。没有合入dev社区功能，没有修改master/dev指针或运行环境。

## 修复前证据

- 四名玩家合法选票2/2/0/0，真实tally_votes淘汰0票玩家，alive、history和实际relay文案一致。
- 投票者输入1时，按插入顺序可能匹配10号。
- 暂停倒数第二票写入后，最后一票先结束，再恢复前者：真实_handle_game_input追加两条历史，轮次1→3。
- 初始回归13项：8 failed、5 passed，覆盖上述缺陷、同账号并发覆盖及退出旧票提前结束。此后补一项真实handler平票测试，共14项新增回归。

## 验收结果

| 标准 | 证据 | 结果 |
|---|---|---|
| AC01 | test_highest_all_81_valid_four_player_ballots、test_highest_tie_real_handler_preserves_zero_vote_players：真实collect/tally/relay与handler；81种合法组合均只淘汰最高票，历史和显示一致 | 通过 |
| AC02 | test_number_*：1/1号/①/空格/10/⑩，拒绝无效、自投、已出局及重复 | 通过 |
| AC03 | test_concurrent_*：真实handler最后两票只结算一次；同账号并发不会覆盖第一张票；连续3次运行两项均通过 | 通过 |
| AC04 | test_completion_*：存活玩家全部提交、下一轮可投、发送不持game_lock | 通过 |
| AC05 | 部署基线全量python -m pytest -q：397 passed；变更严格校验通过，归档验证及最终结果见下文 | 通过 |

## 交付与限制

- 游戏规则、插件规范、CHANGELOG及BOTERO_VERSION同步到1.50.1。
- 定向投票与房间测试17 passed；原始2/2/0/0复现已被81组合及真实handler回归覆盖。
- 临时副本首次归档提示Purpose不足50字，补齐后严格校验1 passed、0 failed；副本保留最终归档任务未勾选，因为未执行真实归档。随后真实归档与实现/测试/规格一起本地提交，不自动推送或合入master/dev。
- 测试使用conftest临时配置、数据库与发送替身，不读取真实对局或调用QQ接口。
- 未进行真实QQ联调；部署应等待当前游戏结束再重启，内存房间不会跨重启恢复。
- 本次不重构描述阶段并发、其他退出规则或消息可靠送达。pytest-asyncio弃用告警来自测试环境，未屏蔽。
