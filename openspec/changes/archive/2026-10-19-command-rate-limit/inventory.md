# 指令入口分类与调度核查

## 分类

- 全部CommandPlugin子类：匹配的消息操作计数。group_review兼有request/notice，但真实post_type检查会排除这些非消息事件。
- 自定义指令类（IS_COMMAND=True，共14类）：ActivityPlugin、AtAllReplyPlugin、BackupPlugin、DicePlugin、FfNewsPlugin、GroupAlarmPlugin、GroupEssencePlugin、ImmortalLotteryPlugin、MonitorPlugin、RecallMessagePlugin、ShopManualRefreshPlugin、TrpgCharPlugin、TrpgPlugin、UpdatePlugin。
- 上述备份、新闻、闹钟、仙人彩同时有心跳逻辑：仅真实消息计数，心跳不计；骰子.r、仙人彩“下注”等非斜杠命令仍按match识别。
- WhoIsSpyPlugin：_mode=command计数，game_input不计（游戏会话输入不是命令匹配）。
- TrpgSessionPlugin：/跑团记录、.dm、.ob计数，普通录制文字不计。
- 非指令10类：AutoFriendPlugin、WelcomePlugin、CheckinRecallPlugin、MessageLoggerPlugin、ForumNotifyPlugin、StartupChangelogPlugin、WeeklyReportPlugin、ShopWeeklyRotationPlugin、WeeklyQuestResetPlugin、ActivityTimerPlugin。

测试test_counting_inventory_covers_every_registered_plugin扫描真实注册表；新增非CommandPlugin而未进入清单会失败，避免新增自定义命令静默漏限流。

## 顺序与例外

采用首次匹配指令时检查、整条事件缓存决定，不提前match所有插件。现有参数解析、权限匹配、handle与内部通知顺序不变，match只执行一次，异常仍经Operation.execute统一记录。未匹配或匹配报错不请求额度；进入handle后失败不退次数。

部分既有心跳match会更新去重时间（如活动计时、论坛通知），本次不改且完全排除限流；不向任何match新增限流写入。

普通消息记录及游戏会话输入不因指令限额停止；禁止的是超限消息匹配的全部指令业务，而不是所有非指令观察行为。

## 协议依据

- OneBot11标准：https://raw.githubusercontent.com/botuniverse/onebot-11/master/message/segment.md （text、at消息段）。
- LLOneBot：https://api.luckylillia.com/schema-189483997.md （at.data.qq为字符串QQ号）。
- LLOneBot：https://api.luckylillia.com/schema-189483988.md （MessageEvent的post_type、user_id、group_id）。

提示复用core.cq.at/text和统一输出模块，不新增OneBot调用。
