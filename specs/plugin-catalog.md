# Spec: 插件注册表

> 关联规范: [plugins.md](plugins.md) | [conventions.md](conventions.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-07-24

全部 38 个已注册插件的完整目录。新增插件时必须在此添加条目。

---

## 消息插件（群聊/私聊指令响应）

| 文件 | 类名 | `name` | 触发方式 | 命令 | 说明 |
|------|------|--------|---------|------|------|
| `call.py` | `CallPlugin` | `call` | CommandPlugin | `小埃同学` / `小埃同學` | 召唤 bot，回复 "我在~" |
| `menu.py` | `MenuPlugin` | `menu` | CommandPlugin | `/菜单` / `/菜單` | 发送 BOT_MENU_TEXT 指令菜单 |
| `checkin.py` | `CheckinPlugin` | `checkin` | CommandPlugin | `/打卡` + 图片 | 打卡：存储图片、解锁称号、计算满勤奖励 |
| `checkin_recall.py` | `CheckinRecallPlugin` | `checkin_recall` | notice 事件 | (notice: group_recall) | 打卡消息被撤回时回滚记录和奖励 |
| `roll_back.py` | `RollbackCheckinPlugin` | `rollback_checkin` | CommandPlugin | `/撤回打卡` | 撤回本周最近一次打卡 |
| `remedy_checkin.py` | `RemedyCheckinPlugin` | `remedy_checkin` | CommandPlugin | `/补卡 YYYY-MM-DD` / `/单日补卡` / `/超级补卡` | 补卡系统：周补卡(6点)、单日补卡(2点)、管理员超级补卡 |
| `all_checkin_display.py` | `AllCheckinDisplay` | `all_checkin_display` | CommandPlugin | `/ALL` | 显示全量打卡图（合并转发） |
| `week_checkin_display.py` | `WeekCheckinDisplayPlugin` | `week_checkin_display` | CommandPlugin | `/本周打卡图` | 显示本周打卡图（私发） |
| `week_list.py` | `WeekListPlugin` | `week_list` | CommandPlugin | `/本周板油` | 显示本周完成打卡的成员列表 |
| `personal_records.py` | `PersonalRecords` | `personal_records` | CommandPlugin | `/档案 [年份]` | 生成年度打卡热力图档案卡 |
| `leaderboard.py` | `LeaderboardPlugin` | `leaderboard` | CommandPlugin | `/排名` / `/rank` | TOP10 积分排行榜 |
| `lottery.py` | `LotteryPlugin` | `lottery` | CommandPlugin | `/抽奖` / `/抽卡` / `/抽卡消费 [@]` | 抽卡系统：消耗积分随机获取奖励 |
| `immortal_lottery.py` | `ImmortalLotteryPlugin` | `immortal_lottery` | 消息 + meta 事件 | `/仙人彩` / `下注 号码` | 仙人彩：每周日 20:00 开奖的彩票系统 |
| `dice.py` | `DicePlugin` | `dice` | 正则 `.r\dd\d` | `.rAdB` 格式 | 掷骰子（如 `.r3d6` 为 3 个 6 面骰） |
| `divination.py` | `DivinationPlugin` | `divination` | CommandPlugin | `/占卜` | 抽取塔罗牌（含正位/逆位解读） |
| `title.py` | `TitlePlugin` | `title` | CommandPlugin | `/称号 [子命令]` `/称号一览` | 称号系统：查看、装备、卸下、详情、随机 |
| `redeem_shop.py` | `RedeemShopPlugin` | `redeem_shop` | CommandPlugin | `/商店 [商品id]` | 积分商店：浏览商品、兑换 |
| `group_alarm.py` | `GroupAlarmPlugin` | `group_alarm` | begin_with + meta | `/闹钟 [参数]` | 闹钟系统：创建、列表、取消，支持循环 |
| `group_essence.py` | `GroupEssencePlugin` | `manage_group_essence` | reply + 文本匹配 | `/加精` `/群精华` `/精华` `/删除精华` | 回复消息设置/取消群精华 |
| `at_all_reply.py` | `AtAllReplyPlugin` | `at_all_reply` | reply + 文本匹配 | `/全体成员` | 回复消息并 @全体成员转发 |
| `recall_message.py` | `RecallMessagePlugin` | `recall_message` | reply + 文本匹配 | `/撤回` | 代用户撤回 bot 自己发送的消息 |
| `set_group_title.py` | `GroupSpecialTitlePlugin` | `group_special_title` | CommandPlugin | `/群头衔 [文本]` | 设置/取消群头衔 |
| `random_reference.py` | `RandomReferencePlugin` | `random_reference` | CommandPlugin | `/随机参考` | 随机返回一张 512×512 参考图 |
| `gallery_login_key.py` | `GalleryLoginKeyPlugin` | `gallery_login_key` | CommandPlugin | `/图库密钥` / `/网页密钥` | 生成打卡图库 Web 端登录密钥 |
| `ff_news.py` | `FfNewsPlugin` | `ff_news` | 完全匹配 + 心跳 | `/FF新闻` | FF14 国服官网最新新闻 |
| `weekly_quest.py` | `WeeklyQuestPlugin` | `weekly_quest` | CommandPlugin | `/周常` | 查看本周打卡/抽奖任务进度 |

## 通知/请求处理插件

| 文件 | 类名 | `name` | 触发 | 说明 |
|------|------|--------|------|------|
| `auto_friend.py` | `AutoFriendPlugin` | `auto_friend` | `request_type == "friend"` | 自动接受好友请求 |
| `welcome.py` | `WelcomePlugin` | `welcome` | `notice_type == "friend_add"` | 好友添加成功后发送私聊欢迎消息 |

## 定时/心跳插件

| 文件 | 类名 | `name` | 基类 | 计划 | 说明 |
|------|------|--------|------|------|------|
| `backup.py` | `BackupPlugin` | `backup` | TimedHeartbeatPlugin | 每天 08:00 | 自动备份打卡图片 |
| `redeem_shop.py` | `ShopWeeklyRotationPlugin` | `shop_weekly_rotation` | TimedHeartbeatPlugin | 每周一 08:00 | 刷新商店货架 |
| `startup_changelog.py` | `StartupChangelogPlugin` | `startup_changelog` | Plugin (手动 meta) | 启动时一次 | 发送开机问候 |
| `weekly_quest.py` | `WeeklyQuestResetPlugin` | `weekly_quest_reset` | TimedHeartbeatPlugin | 每周一 08:00 | 清理过期任务进度 |

## 管理/超级用户插件

| 文件 | 类名 | `name` | 触发 | 权限 | 说明 |
|------|------|--------|------|------|------|
| `grant_points_all.py` | `GrantPointsAllPlugin` | `grant_points_all` | CommandPlugin + `admin_user()` | `/发金币 <数量>` | 给所有用户统一发积分 |
| `monitor.py` | `MonitorPlugin` | `monitor` | `/系统状态` | `super_user()` | 显示运行时间、磁盘、CPU、内存 |
| `update.py` | `UpdatePlugin` | `update` | `/更新` | `super_user()` | git pull 并重启进程 |
| `redeem_shop.py` | `ShopManualRefreshPlugin` | `shop_manual_refresh` | `/刷新商店` | `admin_user()` | 手动刷新商店货架 |

---

## 插件间依赖

部分插件之间存在导入依赖（主要是纯数据/函数导入，非业务逻辑依赖）：

```
title.py (TITLE_DEFS, get_title_def, evaluate_and_unlock_titles, get_lottery_title_ids)
  ├── leaderboard.py      (format_title_prefix)
  ├── checkin.py           (unlock titles on check-in)
  ├── lottery.py           (lottery title pool)
  ├── week_list.py         (format_title_prefix)
  └── redeem_shop.py       (shop title definitions)

bot_menu_text.py (BOT_MENU_TEXT)
  └── menu.py

core.api.py (_build_title_prefix)
  └── plugins.title        (延迟导入: get_title_def)
```

---

## 新增插件检查清单

新增插件时，确保完成以下步骤：

- [ ] 1. 继承 `Plugin` / `CommandPlugin` / `TimedHeartbeatPlugin`
- [ ] 2. 添加 `@register_plugin` 装饰器
- [ ] 3. 设置非空的 `name` 和 `description`
- [ ] 4. 实现 `match()` 和 `handle()`
- [ ] 5. 如需指令，更新 `BOT_MENU_TEXT`
- [ ] 6. 如使用 `on_command`，在 `handle()` 中通过 `self.args` 获取参数
- [ ] 7. 添加 try/except 错误处理
- [ ] 8. 在此文件中添加插件条目
