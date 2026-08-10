# 插件目录与功能包

> 全部 44 个已注册插件、功能包定义、数据依赖

---

## 消息指令插件

| # | 插件名 | 文件 | 触发 | 功能 |
|---|--------|------|------|------|
| 1 | `call` | `call/` | CommandPlugin `小埃同学`/`小埃同學` | 回复"我在~" |
| 2 | `menu` | `menu/` | CommandPlugin `/菜单`/`/菜單` | 发送 BOT_MENU_TEXT（合并转发） |
| 3 | `checkin` | `checkin/` | CommandPlugin `/打卡` + 图片 | 打卡：存储图片、计算奖励、解锁称号 |
| 4 | `checkin_recall` | `checkin_recall/` | notice `group_recall` | 打卡消息被撤回时回滚记录和奖励 |
| 5 | `rollback_checkin` | `roll_back/` | CommandPlugin `/撤回打卡` | 撤回本周最近一次打卡 |
| 6 | `remedy_checkin` | `remedy_checkin/` | CommandPlugin `/补卡`/`/单日补卡`/`/超级补卡` | 补卡系统 |
| 7 | `all_checkin_display` | `all_checkin_display/` | CommandPlugin `/ALL` | 显示全量打卡图和统计（合并转发） |
| 8 | `week_checkin_display` | `week_checkin_display/` | CommandPlugin `/本周打卡图` | 本周打卡图（私发） |
| 9 | `week_list` | `week_list/` | CommandPlugin `/本周板油` | 本周完成打卡的成员列表 |
| 10 | `personal_records` | `personal_records/` | CommandPlugin `/档案 [年份]` | 生成年度热力图档案卡 |
| 11 | `leaderboard` | `leaderboard/` | CommandPlugin `/排名`/`/rank` | TOP10 积分排行榜 |
| 12 | `lottery` | `lottery/` | CommandPlugin `/抽奖`/`/抽卡`/`/抽卡消费`/`/一键抽奖` | 抽卡系统（一键抽奖：连抽今日剩余次数并合并转发结果） |
| 13 | `immortal_lottery` | `immortal_lottery/` | `/仙人彩`/`下注 XXXX` + meta | 仙人彩 |
| 14 | `dice` | `dice/` | 正则 `.r\d+d\d+` | 掷 A 个 B 面骰子（最大 100/1000） |
| 15 | `trpg_dice` | `trpg_dice/` | 正则前缀 `.r/rc/rh` | 跑团骰子系统：DND5E 万能骰点、d20检定、暗骰、属性引用（规则可切换） |
| 16 | `trpg_char` | `trpg_char/` | CommandPlugin `/角色` 前缀匹配 | DND5E 角色卡：查看/列表/切换/删除（创建与编辑引导至网页端，存储层 `core.character_store`） |
| 17 | `divination` | `divination/` | CommandPlugin `/占卜` | 22 张大阿尔卡那 + 正逆位 |
| 18 | `title` | `title/` | CommandPlugin `/称号`/`/稱號` | 称号系统 |
| 19 | `redeem_shop` | `redeem_shop/` | CommandPlugin `/商店 [id]` | 积分商店 |
| 20 | `group_alarm` | `group_alarm/` | begin_with `/闹钟` + meta | 闹钟系统 |
| 21 | `group_essence` | `group_essence/` | reply + `/加精`/`/精华`/`/删除精华` | 设置/取消群精华 |
| 22 | `at_all_reply` | `at_all_reply/` | reply + `/全体成员` | @全体转发回复内容 |
| 23 | `recall_message` | `recall_message/` | reply + `/撤回` | 代撤 bot 消息 |
| 24 | `set_group_title` | `set_group_title/` | CommandPlugin `/群头衔 [文本]` | 设置群头衔（最長 10 字） |
| 25 | `random_reference` | `random_reference/` | CommandPlugin `/随机参考` | picsum.photos 随机 512x512 |
| 26 | `gallery_login_key` | `gallery_login_key/` | CommandPlugin `/图库密钥`/`/网页密钥` | HMAC 登录密钥（仅私聊） |
| 27 | `ff_news` | `ff_news/` | 完全匹配 `/FF新闻` + 心跳 | FF14 国服新闻，每小时自动推送 |
| 28 | `weekly_quest` | `weekly_quest/` | CommandPlugin `/周常` | 查看本周打卡/抽奖任务进度 |
| 29 | `trpg_session` | `trpg_session/` | 消息前缀 `/跑团记录` + 录制期间全匹配 | 跑团聊天记录：录制、合并转发、导出Markdown、浏览 |
| 30 | `who_is_spy` | `who_is_spy/` | 自定义 match: `/创建游戏` `/开始` `/加入` `/离开` `/退出` `/状态` `/放弃` + 私聊游戏阶段输入 | 谁是卧底：群聊创建房间，私聊匿名发言+投票 |
| 31 | `activity` | `activity/` | 自定义 match: 群聊 `/活动` + 私聊 `/提交` | 群活动：接龙（每人限时、机器人接力转发）与匹配下家（圆桌单环，开始通知下家、作品玩家自提，机器人仅记录归档），结束自动归档 |
| 45 | `redeem_code` | `redeem_code/` | CommandPlugin `/兑换码`/`/兌換碼` | 兑换码系统：一次性兑换码，回调发放奖励 |

## 通知/请求处理

| # | 插件名 | 文件 | 触发 | 功能 |
|---|--------|------|------|------|
| 32 | `auto_friend` | `auto_friend/` | `request_type == "friend"` | 自动同意好友请求 |
| 33 | `welcome` | `welcome/` | `notice_type == "friend_add"` | 发送欢迎私聊消息 |

## 定时/心跳

| # | 插件名 | 文件 | 计划 | 功能 |
|---|--------|------|------|------|
| 34 | `backup` | `backup/` | 每天 08:00 | 自动备份打卡图片到本地 |
| 35 | `shop_weekly_rotation` | `redeem_shop/` | 每周一 08:00 | 刷新商店货架 |
| 36 | `startup_changelog` | `startup_changelog/` | 启动后首次 meta | 发送"早上好！小埃同学开机啦" |
| 37 | `weekly_quest_reset` | `weekly_quest/` | 每周一 08:00 | 清理过期任务进度 |
| 38 | `activity_timer` | `activity/` | 每 60 秒（meta 心跳） | 活动计时：接龙超时跳过、匹配截止结束 |

## 管理/超级用户

| # | 插件名 | 文件 | 触发 | 权限 | 功能 |
|---|--------|------|------|------|------|
| 39 | `grant_points_all` | `grant_points_all/` | CommandPlugin `/发金币` | admin_user() | 全员发积分 |
| 40 | `monitor` | `monitor/` | `/系统状态` | super_user() | 运行时间/磁盘/CPU/内存 |
| 41 | `update` | `update/` | `/更新` | super_user() | git pull + os.execv 重启 |
| 42 | `shop_manual_refresh` | `redeem_shop/` | `/刷新商店` | admin_user() | 手动刷新商店 |
| 43 | `group_manager` | `group_manager/` | CommandPlugin `/群插件列表`/`/启用插件`/`/禁用插件`/`/全局插件列表`/`/全局启用`/`/全局禁用` | super_user() | 管理各群插件启用状态 |

## 功能包

定义在 `core/feature_packs/`：

| 功能包 | 包含插件 | 说明 |
|--------|---------|------|
| **基础包** | `checkin`, `checkin_recall`, `roll_back`, `remedy_checkin`, `week_checkin_display`, `all_checkin_display`, `week_list`, `personal_records`, `leaderboard` | 打卡、补卡、撤回、统计、排行 |
| **基础扩展包** | `lottery`, `redeem_shop`, `grant_points_all`, `title`, `weekly_quest`, `immortal_lottery` | 抽奖、商店、称号、周常、仙人彩 |
| **休闲娱乐** | `ff_news`, `group_alarm`, `dice`, `divination`, `random_reference`, `call` | FF14 新闻、闹钟、骰子、占卜、随机图、召唤 |
| **匿名游戏** | `who_is_spy` | 谁是卧底：群聊创建房间，私聊匿名进行 |
| **跑团** | `trpg_dice`, `trpg_session`, `trpg_char` | Sealdice 风格骰子 + 跑团聊天记录 + DND5E 角色卡 |
| **群管理工具** | `group_essence`, `at_all_reply`, `recall_message`, `set_group_title` | 精华、@全体、撤回、头衔 |

**语义：**
- 开启包 = 批量 `INSERT OR IGNORE` 包内每个插件的启用记录（跳过系统插件）
- 关闭包 = 批量 `DELETE` 包内每个插件的启用记录（跳过系统插件）
- 包操作后仍可单独 `/启用插件` / `/禁用插件` 微调
- 系统插件（`SYSTEM_PLUGINS`）不在任何功能包中，始终运行
- 包列表展示：✅ 全部启用 / ⚡ 部分启用 / ❌ 全部禁用

## 插件间数据依赖

```
plugins.title (TITLE_DEFS, evaluate_and_unlock_titles, get_title_def)
  ├──→ plugins.checkin           (打卡时解锁条件称号)
  ├──→ plugins.lottery           (抽卡称号池)
  ├──→ plugins.lottery.rewards
  ├──→ plugins.redeem_shop       (商店称号定价)
  ├──→ plugins.leaderboard       (format_title_prefix)
  ├──→ plugins.week_list         (format_title_prefix)
  └──→ core.api                  (延迟导入，优雅降级)

core.utils (on_quest_trigger, on_quest_rollback)
  ├──→ plugins.checkin           调用 on_quest_trigger("checkin")
  ├──→ plugins.lottery           调用 on_quest_trigger("lottery")
  ├──→ plugins.checkin_recall    调用 on_quest_rollback("checkin")
  └──→ plugins.roll_back         调用 on_quest_rollback("checkin")
```

### 禁用影响速查

| 禁用插件 | 影响 |
|---------|------|
| `title` | 6 个插件的运行时导入仍成功（模块已加载），但称号显示全失；`send_msg` `@`前缀优雅降级 |
| `checkin` | 无打卡数据；lottery 失去每日次数加成；leaderboard 积分排名不准；条件称号不解锁；周常不触发 |
| `lottery` | 抽卡相关条件称号不触发；抽奖周常不触发；商店抽卡商品无实际用途 |
| `weekly_quest` | `/周常` 不可用；但数据仍在积累，条件称号仍能解锁 |

## 废弃模块

| 目录/文件 | 状态 | 说明 |
|-----------|------|------|
| `robot/` | 废弃 | 空目录，无需整理 |
| `core/llm/` | 已弃用 | LLM 对话子系统，代码完整但未集成 |
