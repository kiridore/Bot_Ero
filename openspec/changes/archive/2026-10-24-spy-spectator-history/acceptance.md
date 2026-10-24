# 卧底观战与历史验收

## 基线与边界

基于部署修复60288e2独立实现，版本1.57.0；未混入dev社区功能。全部测试使用conftest/_env临时配置、SQLite和QQ替身。无真实QQ联调，无旧JSON导入、删除或数据重算。

## 逐项结果

| 标准 | 实际命令（python -m pytest … -q） | 结果及验证重点 |
|---|---|---|
| AC01 | test/test_spy_spectating.py | 3 passed；观战接收描述和阶段、拒绝投票；退出停止含延迟通知在内的私聊并可加入其他房间；重入不重复参与记录 |
| AC02 | test/test_spy_vote_visibility.py test/test_who_is_spy_votes.py | 15 passed；两轮现场/历史名单一致，刚出局者仍显示本轮，以后不显示；最高票/编号/收票原子性不回退 |
| AC03 | test/test_spy_history_storage.py | 19 passed；防重/唯一编号/参与经历、原子失败、并发创建及修订号拒绝覆盖；真实生命周期另由AC08覆盖 |
| AC04 | test/test_spy_history_queries.py | 9 passed；真实命令群/本人范围、详情越权拒绝、分页和非法输入、旧语法提示 |
| AC05 | test/test_spy_identity_privacy.py | 4 passed；开局实际私聊无阵营标签，群仅人数；未结束/解散/中断查询不泄密，正常结束揭晓，离房者仅手动查询 |
| AC06 | test/test_spy_history_restart.py | 4 passed；真实main入口恢复一次、重连不重复、失败回滚、旧JSON不读取不更改 |
| AC07 | test/test_spy_history_rewards.py | 4 passed；观战/退出差异、称号阈值、结束/统计/称号统一回滚、重复与发送失败不重奖 |
| AC08 | test/test_spy_room_transitions.py | 9 passed；真实handler并发末票/末描述/重复输入、退出并发、其他房间不被网络等待阻塞、真实命令完整两轮游戏、忽略message_sent、失败不确认；房主转移另保留原三项房间回归 |
| AC09 | python -m pytest -q；openspec validate spy-spectator-history --strict | 全量450 passed，变更严格校验通过；归档及文档检查见下文 |

## 文档与维护

已更新版本/CHANGELOG、菜单、kb/GAMEPLAY、kb/DATABASE、kb/QUICK_REFERENCE、插件目录及specs/plugins/specs/database、知识库索引和roadmap。操作说明：docs/who-is-spy-history.md。

新增表随原数据库备份，没有新服务或后台队列。所有网络发送在事务外；数据失败不假确认、发送失败不重复结算。保留旧统计/称号；新记录不自动清理，未来按运营需要另行确认保留期限。版本跨至1.57.0仅为避开dev已用版本号，不代表社区代码已合入本分支。

## 归档与限制

临时副本归档已成功合并三个新规范，含既有投票规范共4个规范严格校验通过。工具仅提示13项要求可考虑拆分（非阻断），本次按所有者授权作为同一完整功能交付。正式归档与实现同一提交，不自动合并master/dev或推送。

最终卧底相关定向回归70 passed，全量450 passed；本地Markdown链接检查通过，版本与CHANGELOG均为1.57.0。解散指令只发一次群确认；终局私聊只揭晓结果并提供记录指令，不重复发送超长复盘，完整历史使用合并转发。

生产前需另行实际QQ送达与合并转发展示验证；应等进行中游戏结束再重启，新进程不会恢复未完局。后续移植到dev需保留其插件许可/黑名单/限额/统一输出，并包含60288e2投票修复，不能盲目覆盖。
