# BotEro 快速参考

> 项目身份、硬编码常量、路径、完整指令表

---

## 项目身份

- **Bot QQ:** `3915014383`
- **Bot 昵称:** `小埃同学`
- **主人 QQ:** `1057613133`
- **默认群:** `296470819`
- **语言:** Python 3（纯同步、多线程）
- **数据库:** SQLite 3 (`data.db`)
- **入口:** `python main.py`

## 硬编码常量

| 常量 | 文件:行号 | 值 |
|------|----------|-----|
| WebSocket URL | `main.py:14` | `ws://127.0.0.1:3001` |
| WS Token | `main.py:15` | `123456` |
| 默认群号 | `core/context.py:14` | `296470819` |
| 超级用户 | `core/base.py:12` | `[1057613133]` |
| Bot QQ | `core/base.py:13` | `"3915014383"` |
| Bot 昵称 | `core/base.py:11` | `"小埃同学"` |
| 下载代理 | `core/utils.py:53-55` | `127.0.0.1:7890` |
| Python 数据路径 | `core/context.py:10` | `"./server_data"` |
| OneBot 数据路径 | `core/context.py:9` | `"/app/llonebot/server_data"` |
| API 超时 | `core/api.py:43` | 30 秒 |
| 周边界偏移 | `core/utils.py:13-21` | 8 小时 (08:00) |
| 重连延迟 | `main.py:67` | 5 秒 |
| 系统插件（不可禁用） | `core/context.py:19-26` | `menu`, `group_manager`, `startup_changelog`, `backup`, `update`, `auto_friend`, `welcome` |
| 插件命名 | `core/context.py:28-30` | `plugin_key(cls)` = 模块路径二级名（如 `checkin`） |
| 群插件配置表 | `core/db/_base.py:290-295` | `group_plugin_config(group_id, plugin_name)` — 有行=启用 |
| 私聊配置 group_id | `core/context.py:40` | `0` |
| 最大装备称号数 | `plugins/title.py:394` | 3 |
| 群头衔最大长度 | `plugins/set_group_title.py:32` | 10 字符 |
| 年补卡上限 | `plugins/remedy_checkin.py:14` | 4 次 |
| 周补卡费用 | `plugins/remedy_checkin.py:55` | 6 积分 |
| 单日补卡费用 | `plugins/remedy_checkin.py:106` | 2 积分 |

## 常用路径

```
./server_data/                              ← Python 文件 I/O 根目录
  record_images/<user_id>/                  ← 打卡图片缓存（按用户分目录）
  personal_records/                         ← 生成档案图片
  thumb_cache/                              ← Web 端缩略图
  trpg_chars/<user_id>/                     ← 角色卡 JSON：meta.json（current_id/order）+ <char_id>.json
  user_settings/<user_id>.json              ← 个人设置 JSON（文件不存在 = 全默认）
  activity_archive/<活动id>/                ← 活动归档：meta.json + 接龙/匹配 markdown + imgs/

/app/llonebot/server_data/                  ← OneBot API 调用中使用的路径
/var/lib/docker/volumes/onebot_qq_volume/   ← Docker 卷（裸机部署时不用）
```

## 跑团角色卡与个人设置（JSON 存储）

- 角色卡**不再存 SQLite**，改存 `server_data/trpg_chars/<user_id>/`（`meta.json` 记录 `current_id`/`order`，`<char_id>.json` 为单个角色数据）；根目录可用 `BOTERO_TRPG_CHARS_ROOT` 覆盖
- 个人设置存 `server_data/user_settings/<user_id>.json`；根目录可用 `BOTERO_USER_SETTINGS_ROOT` 覆盖
- 已约定设置键：`privacy.char_public`（bool，缺省 True）= 是否允许他人查看我的角色卡（网页端 `/profile/settings` 开关，QQ 查看他人卡需已公开）
- 存储层：`core/character_store.py`、`core/user_settings.py`（原子写 tmp+os.replace，每用户进程内锁；bot 与 web 双进程共用）
- 网页车卡：`/trpg`（管理/编辑）、`/trpg/char/{user_id}/{char_id}`（只读查看）

### 角色卡 JSON 键（5E 主卡面）

- 基础：`char_name`/`race`/`class_name`/`background`/`*_score` 六属性/`proficient_skills`/`hp`/`ac`/`notes`；`race`/`class_name` 限官方清单（`/api/trpg/rules` 的 `races`/`classes`），旧自定义文本仅编辑时追加「（自定义）」选项读侧兼容
- 身份：`alignment`（九宫格组合字符串：守序/中立/混乱 × 善良/中立/邪恶，中立×中立=`绝对中立`，非九宫格可写自定义文本）/`xp`（等级派生源，`level` 由 xp 反推、不入盘编辑）；豁免：`saving_profs`（list[str] 属性名）；战斗：`current_hp`/`temp_hp`/`speed`/`death_saves_success`/`death_saves_fail`/`inspiration`（bool）；资源：`equipment`（list[str]）/`other_proficiencies`/`attacks`（list[str]，`名称|加值|伤害`）/`features`；背景：`personality_traits`/`ideals`/`bonds`/`flaws`
- **派生不入盘**，由 `core/trpg/character.py:finalize()` 计算：`level`（`xp>0` 按 `XP_THRESHOLDS` 20 级阈值表反推，`xp<=0` 回退原 level）、`scores`（基础+种族）、`prof_bonus=2+(level-1)//4`、`save_mods`=属性加值+（豁免熟练?熟练加值:0）、`skill_mods`=属性加值+（技能熟练?2:0）、`passive_perception=10+感知加值+(察觉熟练?2:0)`、`initiative`=敏捷加值、`hit_dice={level}d{职业骰}`；仅 `hp`/`ac` 非零时保留否则计算并写回
- 规则接口 `/api/trpg/rules` 另返回 `xp_thresholds`（经验阈值表）与 `alignments`（九宫格双轴）；旧数据提交（创建/更新）时 `xp<=0 且 level>1` 自动迁移 `xp=阈值下限`；属性生成三方式：购点法（27 点、属性 8-15）、4d6k3 掷骰、标准数组 `[15,14,13,12,10,8]`

## 完整指令表

| 指令 | 作用 | 权限 |
|------|------|------|
| `/菜单` | 显示指令菜单 | 任何人 |
| `/打卡 + 图片` | 打卡 | 任何人 |
| `/ALL` | 全量打卡图 | 任何人 |
| `/本周打卡图` | 本周打卡图（私发） | 任何人 |
| `/本周板油` | 本周打卡成员列表 | 任何人 |
| `/档案 [年份]` | 年度热力图档案 | 任何人 |
| `/排名` / `/rank` | 积分排行榜 TOP10 | 任何人 |
| `/抽奖` / `/抽卡` | 消耗积分抽奖 | 任何人 |
| `/抽卡消费 [@]` | 查询累计抽卡消费 | 任何人 |
| `/发言统计 [@用户]` | 查看本人/他人 今日/本周/本月/今年发言量与活跃天数 | 任何人 |
| `/占卜` | 塔罗牌占卜 | 任何人 |
| `.rAdB` | 掷骰子（基础，旧版） | 任何人 |
| `.r [表达式] [原因]` | 万能骰点（空=D100，支持 +-*/() #多轮 d优势/劣势） | 任何人 |
| `.rc [优势|劣势] <属性/表达式> [豁免]` | DND d20检定（例：`.rc 力量` `.rc 优势 侦查` `.rc 体质 豁免`） | 任何人 |
| `.rh [表达式] [原因]` | 暗骰（群聊提示，私聊结果） | 任何人 |
| `/跑团记录 开始` | 开始录制跑团聊天 | 任何人 |
| `/跑团记录 强制开始` | 强制开始（丢弃未导出的记录） | 任何人 |
| `/跑团记录 结束` | 结束录制并合并转发 | 任何人 |
| `/跑团记录 导出` | 将完成的记录保存到磁盘(Markdown) | 任何人 |
| `/跑团记录 列表` | 查看已保存的记录列表 | 任何人 |
| `/跑团记录 #N` | 查看某次记录的概要信息 | 任何人 |
| `/角色 创建` `/角色 编辑 …` `/角色 放弃` | 回复引导至网页端创建/编辑（https://littlero.tech/trpg） | 任何人 |
| `/角色 查看` | 查看自己的当前角色卡（忽略 @） | 任何人 |
| `/角色 切换 <编号>` | 切换当前角色 | 任何人 |
| `/角色 列表` | 列出我的所有角色 | 任何人 |
| `/角色 删除 <编号>` | 删除角色 | 任何人 |
| `.r 力量` `.r 侦查+10` | 骰子表达式引用角色属性/技能 | 任何人 |
| `/随机参考` | 随机 512x512 图片 | 任何人 |
| `/FF新闻` | FF14 国服新闻 | 任何人 |
| `/商店 [商品id]` | 浏览/兑换商品 | 任何人 |
| `/兑换码 <兑换码>` | 使用兑换码兑换奖励 | 任何人 |
| `/称号 [子命令]` | 称号管理 | 任何人 |
| `/创建游戏 <类型> [人数]` | 群聊创建游戏房间，类型：卧底（默认6人） | 任何人 |
| `/开始 <房间号>` | 群聊开始游戏 | 任何人 |
| `/加入 <房间号>` | 私聊加入游戏房间 | 任何人 |
| `/离开` | 私聊退出房间（仅等待阶段） | 任何人 |
| `/退出` | 私聊退出房间（游戏中弃权出局） | 任何人 |
| `/状态 [房间号]` | 查看房间信息 | 任何人 |
| `/放弃 <房间号>` | 群聊解散房间 | 房主/超管 |
| `/房间列表` | 群聊查看本群所有活跃房间 | 任何人 |
| `/游戏记录 [房间号]` | 群聊查看已保存的游戏记录列表或详情 | 任何人 |
| `/活动 创建 接龙 <标题> [描述] [参数]` | 发布接龙（参数：限时/报名截止/截止，如 `限时 2天`、`报名截止 2026-08-10 20:00`） | 任何人 |
| `/活动 创建 匹配 <标题> [描述] [参数]` | 发布匹配（必填 `截止 <时间>`，可选 `报名截止`） | 任何人 |
| `/活动 加入` / `/活动 退出` | 报名 / 退出活动 | 任何人 |
| `/活动 开始` | 开始活动 | 创建人/超管 |
| `/活动 状态` | 查看活动进度 | 任何人 |
| `/活动 结束` | 结束活动 | 创建人/超管 |
| `/提交 [活动id]` | （私聊）提交作品（重复提交覆盖前一版） | 活动成员 |
| `/闹钟 ...` | 闹钟管理 | 任何人 |
| `/图库密钥` | Web 图库登录密钥 | 任何人（私聊） |
| `小埃同学` | 召唤 bot | 任何人 |
| `/补卡 YYYY-MM-DD` | 周补卡（6 积分） | 任何人 |
| `/单日补卡 YYYY-MM-DD` | 单日补卡（2 积分） | 任何人 |
| `/撤回打卡` | 撤回本周打卡 | 任何人 |
| `/群头衔 [文本]` | 设置群头衔 | 任何人 |
| 回复 + `/加精` | 设精华消息 | 群管理员 |
| 回复 + `/删除精华` | 取消精华 | 群管理员 |
| 回复 + `/全体成员` | @全体转发 | 群管理员 |
| 回复 + `/撤回` | 代撤 bot 消息 | 任何人 |
| `/超级补卡 YYYY-MM-DD [uid]` | 免积分补卡 | 群管理员 |
| `/发金币 <数量>` | 全员发积分 | 群管理员 |
| `/刷新商店` | 手动刷新商店 | 群管理员 |
| `/数据备份` | 手动备份 | 任何人 |
| `/系统状态` | 服务器状态 | 超级用户 |
| `/更新` | git pull + 重启 | 超级用户 |
| `/插件 <name\|列表> [off] [群号]` | 管理插件：列表/启用/禁用 | 超级用户 |
| `/功能包 <name\|列表> [off] [群号]` | 管理功能包：列表/开启/关闭 | 超级用户 |
