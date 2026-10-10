# 消息发送迁移清单

状态：实施中；打卡与两种撤回的发送入口已改为统一输出，并已接入周常/称号/商店的打卡通知。其他发送入口仍待迁移。下表根据当前全部 plugins/**/*.py 的 AST 调用扫描生成后核对，不能以目录不含 send_msg 就断言无间接发送。

## 第一阶段（本提案）

| 文件 | 当前发送方式 | 验证方式 |
|---|---|---|
| plugins/checkin/__init__.py | 已迁移：submit_message + checkin.completed；称号提示由 title/events.py 提交 | 打卡全开/逐一关闭对照，合并文本和 @ 不重复 |
| plugins/checkin_recall/__init__.py | 已迁移：submit_message + checkin.retracted | 群撤回多图与奖励撤销 |
| plugins/roll_back/__init__.py | 已迁移：submit_message + checkin.retracted | 指令撤回、图片结构及奖励撤销 |
| plugins/lottery/__init__.py | 已迁移：submit_message + lottery.draw.requested | 单抽与一键抽奖；称号关闭提前拒绝 |
| plugins/lottery/events.py | 已迁移：output.submit + lottery.draw.completed | 逐次结果、错误提示、合并转发节点与下次抽取 |
| plugins/weekly_quest/__init__.py | 已迁移：submit_message | 任务进度；定时清理无输出 |
| plugins/title/__init__.py | 已迁移：submit_message（含forward） | 称号命令、合并转发、解锁通知 |
| plugins/redeem_shop/__init__.py | 已迁移：submit_message（含forward） | 货架查询、购买、手动刷新、定时刷新；无默认接收方仍刷新但不发公告 |
| plugins/checkin/events.py | 已迁移：全勤奖励提交输出，撤销只按历史记录处理 | 全勤失败不影响其他消费者、新旧领取混合撤销 |
| plugins/weekly_quest/events.py | 已迁移：operation.output.submit 普通文本 | 周常奖励通知、相同标记文本合并 |
| plugins/title/events.py | 已迁移：operation.output.submit 消息段 | 称号通知及用户提及，不作为纯文本拼接 |
| plugins/redeem_shop/events.py | 已迁移：operation.output.submit 普通文本 | 道具奖励通知及重复来源处理 |
| plugins/register/__init__.py | 例外：直接发送（Ruling）——时序敏感的分段对话需段间停顿，统一输出在事件结束时集中送达无法承载；仅限注册流程消息 | 定稿文案逐句、停顿、合并转发协议 |
| plugins/personal_records/events.py | 已迁移：output.submit 消息段（注册资料卡） | 注册完成通知发卡；插件未开放时静默跳过 |

原直接调用中的 checkin → 商店/称号/周常、两撤回 → 周常现已改为通知订阅。lottery 对周常和条件称号的直接调用已改为通知；lottery.rewards 的抽奖奖品（称号及重复返点）属于单抽事务，称号关闭时入口与消费者均拒绝抽奖。打卡全勤奖励现由 checkin/events.py 订阅处理，两种撤回共用其历史清理函数；全勤领取、奖励记录和积分已同事务处理。抽奖的称号奖项不只是展示，详见 implementation-findings.md 的所有者裁定。

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

## 无聊天消息输出的插件（已核查）

| 文件 | 实际操作 | 结论 |
|---|---|---|
| plugins/auto_friend/__init__.py | ApiWrapper.set_friend_add_request → call_api("set_friend_add_request") | 处理好友申请，不是发送聊天消息；不加入文本输出队列 |
| plugins/message_logger/__init__.py | MessageLogManager.insert → 独立日志数据库 | 不发送消息；异常日志不属于 QQ 消息 |

## 间接发送与原始 API 调用核查

| 文件/函数 | 最终 API action | 目标与消息结构、后续验证 |
|---|---|---|
| activity 的实例 _send_private → 模块 _send_private | send_private_msg | 显式 user_id，message 为消息段列表；活动轮转/匹配/私聊提交都须保留目标账号 |
| activity 的实例 _announce_group → 模块 _announce_group | send_group_msg | 显式 group_id，普通文本；不能继承当前私聊作为公告目标 |
| group_alarm._handle_meta_due | send_private_msg / send_group_msg | 来自到期记录的 creator_uid/gid；单次和周期提醒共四条发送路径，保留群提及及 mark_fired/advance 顺序 |
| immortal_lottery 的开奖通知 | send_group_msg | 显式开奖结果所属 group_id，普通文本；不是发送到心跳的默认位置 |
| trpg_session._send_forward | send_group_forward_msg | 显式 group_id；nodes 含 user_id/nickname/content，保持录制条目发送者 |
| who_is_spy._send_private 与游戏开始/加入群提示 | send_private_msg / send_group_msg | 玩家账号与房间群号分别传入，不按当前私聊盲目推断 |
| who_is_spy.relay.broadcast | send_private_msg | 逐玩家私聊；include_dead 控制是否包含已出局玩家 |
| relay 的 broadcast_descriptions / broadcast_vote_instructions / broadcast_describe_instructions / broadcast_game_over | 经 broadcast → send_private_msg | 每名玩家独立接收；保留各自消息段及 include_dead 差异 |
| relay.broadcast_vote_result | broadcast + send_private_msg | 全员投票结果之外，还单独给出局者私聊提醒，不能误合并成群消息 |
| relay.send_forward_to_group | send_group_forward_msg | 显式房间群号和预构造节点；build_forward_nodes 只构造数据，不发送 |

当前全量 AST 扫描发现原始 call_api 分布在六个插件文件中，action 均为字面量 send_private_msg、send_group_msg、send_group_forward_msg；没有动态 action。另用全文检索核查 requests.post/request、直接 .send、getattr 动态发送和导入发送函数，未发现 plugins 下绕过这些路径的额外网络发送。这个结果不替代将来新增代码的审查；动态 action 或新增发送文件会使清单测试失败。

最终迁移要求插件不再直接调用发送 API；底层 ApiWrapper 保留真实发送能力，不属于遗留业务入口。

## 1.1 处理顺序与既有奖励条件核查

| 实际文件 | 核查结果与必须保持的条件 | 对照测试 |
|---|---|---|
| main.py / core/base.py / core/context.py | 外部事件一个线程；顺序创建插件实例；不是每个插件一个线程。系统插件始终运行；群/账号设置在操作开始时固定；未采用 economy_active 或按包名决定联动 | test_plugin_dispatch.py、test_plugin_controls.py |
| core/api.py / core/message_output.py | send_msg 优先群、其次私聊、无目标才回落配置默认群；提及前注入称号；send_forward_msg 构造节点，send_forward_nodes 使用已有节点；发送结果为0视为失败，不重执行业务 | test_api_send_fallback.py、test_title_prefix_hook.py、test_plugin_output.py |
| plugins/checkin/__init__.py | 图片必填；保存打卡及图片→时间线上报→完成通知及回执；全勤消费者执行原有规则。周界仍为周一08:00；月全勤+1仍受本周首次打卡与旧 full_month_weekly_check 领取条件限制，本任务不修订这条条件 | test_checkin_privacy.py、test_plugin_event_integration.py |
| plugins/redeem_shop/events.py | 先消费幸运道具，再按10%概率决定+1；与道具消耗同事务；该消费者先于称号和周常 | test_plugin_event_integration.py 的道具关闭/重复来源断言 |
| plugins/title/logic.py、events.py | 时段/日期、打卡累计、抽奖画像、周常历史、称号收藏与装备共同决定解锁；打卡的称号评估必须先于本次周常次数更新，不能因重构提前解锁 | test_plugin_event_integration.py::test_title_evaluation_precedes_new_quest_completion |
| plugins/weekly_quest/engine.py / core/db/quest.py | 打卡1/3/7天分别奖励1/2/3；抽奖3/7/15次分别奖励1/2/5；按账号/任务/周领取一次；全清要求全部六任务。回退不减少累计完成和历史全清次数 | test_plugin_migration_baseline.py、test_reward_compatibility.py |
| plugins/checkin_recall/__init__.py / plugins/roll_back/__init__.py | 消息撤回按message_id删除该消息全部图片；指令撤回删除本周最近一条记录并显示图片。保留两者现有粒度差异；撤销周常和全勤，不删除已拥有称号 | test_plugin_event_integration.py、test_reward_compatibility.py |
| plugins/lottery/__init__.py | 上限：未打卡2次、已打卡5次，另叠加商店加成；首抽免费，之后每次1积分。原顺序为费用/次数→周常→奖品/画像→称号→流水；现将费用、次数、奖品、画像、流水、来源记录原子提交，再通知周常→条件称号→输出与下次抽取。保持称号晚于本次周常，下一次抽取可使用本次周常奖励；一键抽奖逐次处理，积分不足停止 | test_lottery_bulk.py，称号关闭的拒绝必须早于上述所有写入 |
| plugins/lottery/rewards.py | 积分奖项合计79%；普通/稀有/传奇称号12%/5%/4%；重复称号返1/2/3积分。draw_reward 不只是读奖表，会直接写称号和返点，后续不可当作纯抽样函数迁移 | test_plugin_migration_baseline.py 的奖表与重复称号对照 |
| plugins/redeem_shop/__init__.py、logic.py / core/db/shop.py | 货架全局单份；随机4个称号，各库存2，稀有度售价3/6/10。功能商品价格6/2/3/1；商店直接写称号、打卡道具、抽奖道具和次数。redeem 中扣分/扣库存/发商品按原事务处理 | test_shop_shelf.py（已有）、test_plugin_migration_baseline.py |

两种撤回的全勤重复代码已合并，但保留不同业务周/自然周的旧时间范围。抽奖消费商店道具现遵守商店开关，关闭时不使用加成或消耗道具，已存权益保留。最终验收已补齐商店称号商品开关检查：称号关闭时在扣费/扣库存前拒绝；其他商品不受影响。已消费道具不因奖励通知失败再次消耗。此前“全部耦合只有八处”的说法不完整，以上实际数据库写入同样属于后续迁移范围。

## 1.2 清单覆盖检查

`python -m pytest test/test_plugin_migration_inventory.py -q` 解析全部 plugins/**/*.py，核对每个直接发送或新输出提交文件均在上表；动态 call_api action 必须重新人工核查。该检查不导入插件、不访问生产数据库。文本/图片/提及/转发及显式私聊群聊目的地均列有验证方法；阶段二、三尚未实施，不标完成。

## 1.3 权威上游与架构约束核查

已通过 HTTP 拉取并阅读下列权威单页，未依赖搜索摘要；引用依据记录于本提案，后续修改其他扩展接口必须另查对应单页。

| 页面 | 本次采用的事实 |
|---|---|
| https://raw.githubusercontent.com/botuniverse/onebot-11/master/api/public.md | send_group_msg 使用 group_id，send_private_msg 使用 user_id；message 可用数组；set_friend_add_request 是申请处理而非消息发送 |
| https://api.luckylillia.com/schema-189483988.md | MessageEvent 的群号仅群消息存在；账号与message_id为独立字段，message为消息段数组 |
| https://api.luckylillia.com/schema-189483978.md | GroupRecallNoticeEvent 的 user_id 为原消息发送者，operator_id 为执行撤回的人，message_id 标识被撤回消息 |
| https://api.luckylillia.com/schema-189483991.md | TextSegment 为 type=text、data.text 字符串 |
| https://api.luckylillia.com/api-226194727.md | 私聊发送需明确 user_id 和 message，响应 data.message_id 用于确认结果 |
| https://api.luckylillia.com/schema-189484004.md | NodeSegment 支持已有消息id或自定义content；OneBot字段为user_id/nickname，同时列出uin/name兼容字段 |
| https://api.luckylillia.com/api-226189040.md | 私聊合并转发使用user_id与messages节点数组；迁移保留正文构造方式，由现有ApiWrapper包装 |
| https://api.luckylillia.com/api-226189162.md | 群合并转发需group_id和messages节点数组；示例采用uin/name，不能因此把已有OneBot节点擅自全部改名 |

specs/architecture.md 已纠正错误的每插件线程描述，specs/plugins.md 已记录同步通知、成功后确认输出、快照与历史奖励清理要求。所有者仅授权本次私有版开关语义和消息合并变化，未授权改概率、价格或扩大社区首版范围。
