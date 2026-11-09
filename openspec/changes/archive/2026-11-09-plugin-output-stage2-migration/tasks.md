# 任务：插件消息输出迁移（第二阶段 + 新闻/兑换码）

按设计文档第 6 节的顺序执行。对应验收标准见 proposal.md。

## 第一组：简单文本与双目标

- [x] T1 `plugins/trpg_char/__init__.py`：10 处当前会话回执改 `submit_message`（AC08）
- [x] T2 `plugins/trpg_dice/__init__.py`：明骰回执改 `submit_message`；暗骰群提示 + 私聊结果双目标显式提交，保留不泄露约束（AC08）

## 第二组：回执为主

- [x] T3 `plugins/redeem_code/__init__.py`：提示改 `submit_message`（保留 `@`），`delete_msg` 不动（AC07）
- [x] T4 `plugins/group_alarm/__init__.py`：回执改 `submit_message`；到期通知按闹钟目标显式提交（AC05）
- [x] T5 `plugins/immortal_lottery/__init__.py`：下注/查询回执改 `submit_message`；开奖按群号显式提交（AC05）

## 第三组：转发与定时

- [x] T6 `plugins/trpg_session/__init__.py`：回执改 `submit_message`；`_send_forward` 改 `kind="nodes"` 显式群目标（AC08）
- [x] T7 `plugins/activity/__init__.py`：`_send_private`/`_announce_group` 改接 `operation`；定时事件显式群目标；保留进行中不外发他人提交内容（AC04）

## 第四组：推送

- [x] T8 `plugins/news/__init__.py`：9 处回执改 `submit_message`；推送改为显式默认群目标提交（所有者选定 A：失败不重试、游标照常推进）（AC06）

## 第五组：卧底

- [x] T9 `plugins/who_is_spy/relay.py`：`GameMessenger` 改持 `operation`；移除 `send` 的 `call_api` 分支；保留黑名单快照、`can_receive`、出局静默三项判断（AC02、AC03）
- [x] T10 `plugins/who_is_spy/__init__.py`：`_reply` 改提交（含转发节点）；`emit` 传入 `operation`（AC02）

## 收尾

- [x] T11 迁移清单：`migration.md` 第二阶段表格标记为已完成，`news`/`redeem_code` 登记为同步迁移（AC01）
- [x] T12 测试同步：`test/helper.py` 新增 `RecordingOutput`/`bind_output` 供直接构造的插件使用；受影响测试改为校验输出提交；`test_plugin_migration_inventory.py` 通过（AC01）
- [x] T13 `CHANGELOG.md` `[未发布]` 记内部重构与已知限制（不 bump 版本）
- [x] T14 全量 `python -m pytest`（961 passed）+ `openspec validate --all --strict`（25 passed）+ `git diff --check` 通过（AC09、AC10）

## 执行记录

- 迁移按风险从低到高推进，每组完成后跑定向测试。全量首次 11 项失败均属测试同步问题（直接构造插件缺操作上下文、断言仍指向 `api.*`），修正后全量 961 通过。
- 一处测试语义调整：`test_network_wait_does_not_block_other_rooms` 原本模拟发送阻塞，迁移后用真实 `MessageOutput` 验证“提交不触发网络、flush 时才发送”。
- 一处工具失误：批量脚本的替换串导致 3 个测试文件 import 行损坏，已用 git 恢复后重做，最终语法与测试均通过。
