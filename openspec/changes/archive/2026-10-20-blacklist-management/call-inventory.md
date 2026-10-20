# 黑名单执行路径核查

本表覆盖QQ机器人进程及其心跳处理。不是网页用户认证改造，不新增Web管理面板；单独网页服务的权限不凭此表宣称已改变。

## 新操作与状态修改

| 路径 | 判定位置及处理 |
|---|---|
| main.plugin_pool普通消息 | 注册提醒和指令限额之前原子获准；同一Operation及ApiWrapper持有快照 |
| 普通CommandPlugin及自定义指令 | 来源账号/群由入口限制；同一指令已开始后批量/通知沿用快照 |
| grant_points_all → points.grant_all | 正负积分排除快照账号，回执按实际人数；同事务回滚 |
| remedy_checkin周补/单日/超级补卡 | 管理员代操作另外检查目标账号，阻止给被封目标新增记录或扣费；自身调用仍受入口限制 |
| activity私聊提交 | 解析真实活动所属群，用原快照筛选；被封群活动不能通过私聊提交绕过，下载/写入前拒绝 |
| who_is_spy私聊加入/退出/状态/游戏输入 | 解析房间所属群，用原快照限制；不得通过私聊修改被封群房间 |
| trpg_session | 录制及角色管理使用事件所属群；私聊不启动群录制，无另选群写入路径 |
| 群审核 | 旧配置保持原检查；新开关启用使用本操作快照，后续预留审批传同一快照 |
| 所有应用内ban/unban | CommunityManager写入与准入共用锁，锁不跨业务或网络；外部直接编辑数据库不承诺运行期排序 |

## 奖励、既有权益与清理

| 路径 | 处理 |
|---|---|
| checkin → checkin/weekly_quest/title/redeem_shop events | payload由本操作账号产生，来源操作先获准；内部通知不重读封禁，已有操作完成 |
| lottery.engine/rewards/events | 当前账号扣费、奖品、道具及流水同事务；批量抽奖仍属于同一获准操作 |
| redeem_shop.logic / redeem_code.codes | 当前请求账号权益，入口拒绝新被封操作；不属于跨账号批量发奖 |
| title.logic | 正常调用来自当前账号操作；卧底跨账号入口另外过滤 |
| who_is_spy → grant_game_titles | 正常群参与者战绩照记，快照内被封账号allow_titles=False，不授新免费称号 |
| immortal.finalize_draw | 正常群已有付费承诺不按参与者封禁剔除，事务及防重复保留；被封群不获准开奖 |
| checkin_recall → cleanup订阅 | 真实撤回仅允许部署许可中的记录清理及cleanup消费者，无用户输出，包括失败输出；重复撤销不重复扣 |
| 主动roll_back | 普通指令，不能借历史清理例外绕过来源封禁 |

## 所有直接私聊发送文件

以下清单由test_blacklist_call_inventory.py扫描校验；不能只检查群消息入口。

| 文件 | 接收账号与限制 |
|---|---|
| plugins/register/__init__.py | 当前请求账号，入口及原操作快照；登记过程不因中途新增封禁中断 |
| plugins/welcome/__init__.py | friend_add账号，事件入口禁止被封账号欢迎 |
| plugins/week_checkin_display/__init__.py | 当前请求者；入口获准，不替任意第三人发送 |
| plugins/trpg_dice/__init__.py | 当前掷骰者的私密结果；入口获准 |
| plugins/group_alarm/__init__.py | 私聊记录创建者，逐条任务准入；群记录按群准入 |
| plugins/activity/__init__.py | 参与者由_send_private按当前API的操作/活动记录快照过滤 |
| plugins/who_is_spy/__init__.py | 发词及称号等定向私聊，按操作快照过滤 |
| plugins/who_is_spy/relay.py | 广播、出局和结束通知，按同一快照过滤 |

统一输出的默认目标是原事件目标；注册资料卡、打卡/抽奖/称号消息对应本操作账号。group_review的额外私聊目标为当前超管，受身份保护；容量回执邀请人在获准请求快照内。main的注册提醒在封禁检查后。core/api.send_msg等原位置路由不改成第二次动态读取，避免中途截断已获准操作。

## 心跳全部类别

| 类别 | 任务单位/行为 |
|---|---|
| group_alarm | 每条闹钟：按群或私聊创建者；拒绝不标记、不推进 |
| activity | 每条活动：按群；同轮open→running复用同一记录快照，参与者私聊另过滤 |
| immortal_lottery | 每群/期：保留被封群待结算注单，正常群履行既有付费权益 |
| ff_news | 默认群小时任务：获准后请求官网 |
| weekly_report | 目标群/周：获准后生成、写库、公告 |
| forum_notify | 每条新帖：获准后通知并标记；全局过期投票清理继续 |
| redeem_shop | 全局货架继续刷新，公告目标另外获准 |
| backup | 图片维护继续，定时群公告另获准；人工命令用原消息准入 |
| startup_changelog | 群公告获准才发送，未发不置成功标记 |
| weekly_quest清理 | 全局过期进度维护，无新奖励，不因单账号/群停止 |

## 解除恢复

解除只删blacklist行；注册、群审核、插件设置、奖励和待处理任务不变。恢复按原到期查询执行，不新增追补任务。已错过窗口的仙人彩保持原窗口约束与未结算数据；不自动退款、作废或补开奖。

证据：test_blacklist_recovery.py（真实main的资格恢复与代操作限制）、test_blacklist_tasks.py（单次/循环闹钟、仙人彩、重复执行）、test_blacklist_activity_game.py（活动和免费称号）、test_blacklist_notifications.py（定向通知与共享维护）。协议来源见protocol-check.md。
