# 消息发送迁移清单

状态：实施中；尚无插件标为迁移完成。下表根据当前全部 plugins/**/*.py 的 AST 调用扫描生成后核对，不能以目录不含 send_msg 就断言无间接发送。

## 第一阶段（本提案）

| 文件 | 当前发送方式 | 验证方式 |
|---|---|---|
| plugins/checkin/__init__.py | send_msg：失败提示、称号提示、打卡回执 | 打卡全开/逐一关闭对照，合并文本和 @ 不重复 |
| plugins/checkin_recall/__init__.py | send_msg：撤回通知 | 群撤回多图与奖励撤销 |
| plugins/roll_back/__init__.py | send_msg：提示与图片 | 指令撤回、图片结构及奖励撤销 |
| plugins/lottery/__init__.py | send_msg、send_forward_nodes | 单抽与一键抽奖；称号关闭提前拒绝 |
| plugins/weekly_quest/__init__.py | send_msg | 任务进度；定时清理无输出 |
| plugins/title/__init__.py | send_msg、send_forward_msg | 所有称号管理分支、合并转发、解锁通知 |
| plugins/redeem_shop/__init__.py | send_msg、send_forward_msg | 货架查询、购买、手动刷新、定时刷新 |

间接业务调用：checkin → shop.pop_luck / title.evaluate_and_unlock_titles / weekly_quest.on_quest_trigger；两撤回 → weekly_quest.on_quest_rollback；lottery → weekly_quest.on_quest_trigger / title.evaluate_and_unlock_titles；lottery.rewards → titles.unlock 与重复称号返点。打卡的全勤奖励与撤销重复代码属于本次事务与兼容测试范围。抽奖的称号奖项不只是展示，详见 implementation-findings.md 的所有者裁定。

## 后续第二阶段（必须另建提案）

| 文件 | 当前发送方式 | 验证方式 |
|---|---|---|
| plugins/who_is_spy/__init__.py | send_msg、call_api、_send_private | 群和多账号私聊隔离、游戏结算称号通知 |
| plugins/who_is_spy/relay.py | call_api | 每个玩家目标与消息结构保持 |
| plugins/activity/__init__.py | send_msg、call_api（含包装发送） | 群操作、私聊提交、定时事件、显式接收方 |
| plugins/group_alarm/__init__.py | send_msg、call_api | 创建/取消/查询、到期群和私聊通知 |
| plugins/immortal_lottery/__init__.py | send_msg、call_api | 下注与定时开奖目标、奖励不重复 |
| plugins/trpg_session/__init__.py | send_msg、call_api | 记录开始/结束/导出及转发结构 |
| plugins/trpg_char/__init__.py | send_msg | 角色命令所有分支 |
| plugins/trpg_dice/__init__.py | send_msg、send_private_msg | 明骰/暗骰，不泄露私聊结果 |

## 后续第三阶段（必须全部完成，不长期保留旧入口）

| 文件 | 当前发送方式 | 验证方式 |
|---|---|---|
| plugins/all_checkin_display/__init__.py | send_msg、send_forward_msg | 空数据与转发图表 |
| plugins/at_all_reply/__init__.py | send_msg | 回复、全体提及保持结构 |
| plugins/backup/__init__.py | send_msg | 手动和心跳备份 |
| plugins/call/__init__.py | send_msg | 昵称召唤 |
| plugins/dice/__init__.py | send_msg | 掷骰和错误输入；不删除插件 |
| plugins/divination/__init__.py | send_msg | 图文结果 |
| plugins/ff_news/__init__.py | send_msg | 手动新闻与整点推送 |
| plugins/forum_notify/__init__.py | send_msg | 定时通知接收方 |
| plugins/gallery_login_key/__init__.py | send_msg | 密钥不得合并进入群消息 |
| plugins/grant_points_all/__init__.py | send_msg | 权限、错误和发放回执 |
| plugins/group_essence/__init__.py | send_msg | 加精/删除精华分支 |
| plugins/group_manager/__init__.py | send_msg | 管理指令及权限拒绝 |
| plugins/leaderboard/__init__.py | send_msg | 私聊/群聊与空榜 |
| plugins/menu/__init__.py | send_forward_msg | 文案包和转发结构 |
| plugins/monitor/__init__.py | send_msg | 系统状态与权限 |
| plugins/personal_records/__init__.py | send_msg | 图文档案 |
| plugins/random_reference/__init__.py | send_msg | 图片和失败提示 |
| plugins/recall_message/__init__.py | send_msg | 回复撤回操作结果 |
| plugins/redeem_code/__init__.py | send_msg | 核销成功/重复/错误 |
| plugins/remedy_checkin/__init__.py | send_msg | 普通和管理员补卡所有路径 |
| plugins/set_group_title/__init__.py | send_msg | 头衔修改与取消 |
| plugins/startup_changelog/__init__.py | send_msg | 启动公告一次发送 |
| plugins/update/__init__.py | send_msg | 重启前提示确实发送，不在重启后丢失 |
| plugins/week_checkin_display/__init__.py | send_msg、send_private_msg | 图片接收方和无图提示 |
| plugins/week_list/__init__.py | send_msg | 名单与称号展示 |
| plugins/weekly_report/__init__.py | send_msg | 启动补偿和周一定时发布 |
| plugins/welcome/__init__.py | send_private_msg | 入群用户私聊隔离 |

扫描未发现直接发送调用的 auto_friend、message_logger 也须核查其 API 封装；接受好友请求不是聊天消息，不能错误排队为文本。扫描必须复查本地包装函数（如 _send_private）及原始 call_api 的具体 action。最终验收要求插件不再直接调用发送 API；底层 API 自身保留真实发送能力，不属于遗留业务入口。

## 当前核查证据

- main.py：每个外部事件创建线程，plugin_pool 在该线程顺序遍历。
- 两种撤回打卡方式不删除已拥有称号，任务累计完成和历史全清不因撤销积分减少。
- 群/私聊公共设置目前只有开启行，账号显式关闭需要新增三态覆盖表。
- 已查阅上游 TextSegment schema 与发送私聊文本接口；其他消息/事件结构在编辑对应路径前继续查阅。
