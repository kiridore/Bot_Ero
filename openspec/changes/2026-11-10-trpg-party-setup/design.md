# 设计：跑团开团前准备与准入校验

## 1. 已确认决策

| 编号 | 决策 | 来源 |
|---|---|---|
| D1 | 校验集合 = 全体群成员（运营模型：一个群只跑一场团，群名即团名，群成员即 DM+PL+OB+机器人） | 所有者 Q1:A |
| D2 | 准备情况卡片实时刷新，DM 自行决定何时开录 | Q2:A |
| D3 | `.dm` 自封、DM 唯一（后设顶掉先设）、只有 DM 能开录、超级用户可代开 | Q3:A |
| D4 | DM 与观察者不需要准备；**DM 也不需要角色卡** | Q4:A + 补充 |
| D5 | 准备时绑定账号当前角色卡并快照进名单 | Q5:A |
| D6 | 成员列表不可达时拒绝开录并说明原因，`强制开始` 可绕过 | Q6:A |
| D7 | 准备名单与角色标记落盘 `pending.json` | Q7:B |
| D8 | 旧 `/跑团记录` 彻底停用，无提示桩 | Q8:B |
| D9 | 旧 `/角色` 彻底迁移为 `/跑团 角色`，不再响应 | Q9:C |
| D10 | 拒绝开录时一条消息列出全部缺失项 | Q10 推荐 |

## 2. 指令树与路由划分

```
/跑团                      准备情况卡片（同 /跑团 名单）
/跑团 准备                 玩家准备
/跑团 取消准备             撤销准备
/跑团 名单                 打印准备情况卡片
/跑团 记录 开始            仅 DM，通过准入校验
/跑团 记录 强制开始         跳过校验
/跑团 记录 结束            结束录制
/跑团 记录 导出            生成 record.md
/跑团 记录 列表            该群已落盘记录
/跑团 记录 #N              第 N 条记录概要
/跑团 角色 查看            当前角色卡
/跑团 角色 列表            我的全部角色卡
/跑团 角色 切换 <编号>      设为当前角色
/跑团 角色 删除 <编号>      删除角色卡
```

`.dm` / `.ob` 保持独立指令，不改名。

**路由划分**（两个插件都匹配 `/跑团` 前缀，各自只处理自己的子命令；`match()` 无副作用）：

| 插件 | 负责 | 匹配条件 |
|---|---|---|
| `plugins/trpg_session` | 裸 `/跑团`、`准备`、`取消准备`、`名单`、`记录 …` | 首段为 `/跑团`，第二段为空或属于 `{准备, 取消准备, 名单, 记录}` |
| `plugins/trpg_char` | `角色 …` | 首段 `/跑团` 且第二段为 `角色` |

其余形如 `/跑团 xxx` 的消息两个插件都不响应（不抢别人指令）。旧 `/跑团记录`、`/角色` 前缀不再出现在任何 `match()` 中。

## 3. 数据：`pending.json`

路径：`server_data/trpg_records/<群号>/pending.json`（与记录目录同根；目录不存在时创建）。

```json
{
  "version": 1,
  "group_id": 123456789,
  "roles": { "111111": "dm", "222222": "ob" },
  "prepared": {
    "333333": {
      "user_id": "333333",
      "nickname": "小王",
      "char_id": 2,
      "char_name": "艾拉",
      "race": "精灵",
      "class_name": "游侠",
      "level": 3,
      "prepared_at": "2026-11-10 20:01:00"
    }
  }
}
```

- 读写集中在新模块 `core/trpg/party.py`：`pending_path(group_id)`、`read_pending(group_id)`、`write_pending(group_id, data)`、`default_pending(group_id)`。
- 写用 tmp + `os.replace` 原子替换；读失败/损坏/`version` 不符 → 返回默认空结构并记一条 warning，不抛异常。
- 角色标记与准备名单**同文件**：设 `.dm`/`.ob` 与 `/跑团 准备` 都走"读 → 改 → 原子写"。
- 录制开始时清空：删除该文件（等价于全员未准备、无标记）。第 N 次团（同群复用）天然从空开始。

## 4. 成员名单接口

`core/onebot_client.fetch_group_members(group_id) -> list[dict] | None`

- HTTP `POST <onebot_http_url>/get_group_member_list`，body `{group_id, no_cache: false}`，超时 5 秒（复用 `_session`，`trust_env=False`）。
- 返回规范化后的数组：`[{"user_id": str, "nickname": str, "is_robot": bool}]`，昵称取 `card_or_nickname` → `card` → `nickname` → QQ 号。
- 上游确认：LLOneBot 该接口返回数组，字段含 `user_id` / `nickname` / `card` / `card_or_nickname` / `is_robot`（`specs/llms.txt` 第 34 条，2026-11-10 查证）。
- 失败（网络/非 2xx/`status != ok`/`data` 非数组）返回 `None`，与"返回空数组"区分。
- 需要把 `_call_onebot` 的返回判定从"仅 dict"放宽为"dict 或 list"，否则数组会被吞成 `{}`。

## 5. 校验算法（`/跑团 记录 开始`）

```
执行人 = 事件发送者
若 执行人 不是 DM 且不在超级用户名单：回「只有 DM 才能开始录制」并结束
若 该群已在录制中：回「当前已在录制中」并结束
members = fetch_group_members(group_id)
若 members 为 None：回「无法获取群成员列表，OneBot 未响应（可让 DM 使用 /跑团 记录 强制开始）」并结束
member_ids = {m.user_id for m in members if not m.is_robot and m.user_id != BOT_QQ}
roles = read_pending(group_id).roles，仅保留 member_ids 内的
dm_ids = [uid for uid, r in roles.items() if r == "dm"]
ob_ids = [uid for uid, r in roles.items() if r == "ob"]
players = member_ids − {dm}
players_without_ob = players − ob_ids

problems = []
若 len(dm_ids) != 1：problems += 「还没有 DM：请一人发送 .dm」（0 人）或「DM 标记异常」（>1，理论上被"后设顶掉"保证不会出现）
对 players_without_ob 中每人：
    若 get_current(uid) 为空：缺卡列表
    若 uid 不在 prepared：未准备列表
若 problems 非空：把四类缺失（缺 DM / 缺卡 / 未准备 / 成员列表不可达）合并成一条消息发出，结束
否则：写记录、清空 pending、回执并开始录制
```

要点：

- **观察者豁免**：`ob_ids` 内的人既不要求角色卡也不要求准备，但仍在成员名单里（卡片会显示）。
- **DM 豁免**：不要求角色卡、不要求准备；DM 本人也可以是超级用户。
- **机器人豁免**：`BOT_QQ` 与 `is_robot` 成员不入校验集合。
- **已退群的人**：`roles` / `prepared` 中残留但不在 `member_ids` 的记录被忽略，不报错、不主动清理。
- 所有 `character_store.get_current` 调用都是文件读，成员数几十人时可接受（一次开录几十次文件读）。

### 失败消息格式

```
无法开始录制，请先处理：
· 还没有 DM：请一人发送 .dm
· 缺少角色卡（到 https://littlero.tech/trpg 创建）：@小王 @小李
· 尚未准备：@小王 @小李（发送 /跑团 准备）
```

无问题时卡片：

```
【夜航团】开团准备
DM：老张
观察者：小美
已准备 2/3：
· 小王 → 艾拉（精灵 游侠 Lv.3）
· 小李 → 阿铁（人类 战士 Lv.2）
未准备：@小张
```

（团名取 `get_group_info` 的群名；取不到时用 `群 <群号>`。）

## 6. 准备与卡片

- `/跑团 准备`：当前角色卡为空 → 回车卡链接，不写名单；否则把 `char_id/char_name/race/class_name/level` 快照写入 `prepared[uid]`，昵称取事件里的群名片，写盘后**输出刷新后的卡片**。
- `/跑团 取消准备`：删除 `prepared[uid]`，写盘，输出卡片。
- `/跑团 名单` 与裸 `/跑团`：直接输出卡片（需要拉成员名单来判断"未准备"，`fetch_group_members` 失败时卡片只显示已准备者并标注「成员名单不可用」）。
- `.dm` / `.ob` 后同样输出刷新后的卡片（DA 2 的"实时卡片"）。
- 卡片本身**不推送**给未参与的人（不 @ 全员），只在触发指令时输出。

## 7. 录制期间的行为

- `/跑团 准备`、`/跑团 取消准备`、`/跑团 名单`：回「录制中无法准备/查看准备名单」。
- `/跑团 记录 开始`：回「当前已在录制中」。
- `.dm` / `.ob` 录制中仍可用：更新 `meta.json.roles`（沿用 1.62.0 行为），同时更新 `pending.json`（该文件此时已清空 → 会重建，只含 roles）。为避免录制中产生无用文件，录制中改角色只写记录 `meta.json`，**不写** `pending.json`。
- `record_bot_message` 已覆盖这些提示语（录制中它们会出现在记录里，属预期）。

## 8. 开录写入记录

- `_start_session` 新增参数 `roster`（准备名单快照）与 `roles`：
  - `meta.participants` = 名单全员（`user_id/nickname/char_name/role`），按 `prepared_at` 升序，DM 放首位；
  - `meta.roles` = 当时的 DM/OB 标记（仅群成员内）；
  - 会话内存里的 `participants` 同步预置，会话 `roles` 取 `meta.roles`。
- 之后 `_record_user_message` 只补充名单外的人（`is_new` 逻辑不变）。
- 开录成功 → 删除 `pending.json`。

## 9. 影响面（必须一并处理）

| 位置 | 改动 |
|---|---|
| `core/trpg/party.py`（新增） | `pending.json` 路径与读写、默认结构 |
| `core/onebot_client.py` | `_call_onebot` 支持数组 `data`；新增 `fetch_group_members` |
| `plugins/trpg_session/__init__.py` | 指令树改为 `/跑团 …`；准备/取消/名单/卡片；开录校验；开录预置名单；录制中拦截准备类指令；`.dm/.ob` 改为写 `pending.json`（录制中只写 meta） |
| `plugins/trpg_char/__init__.py` | 指令 `/角色 …` → `/跑团 角色 …` |
| `plugins/menu/bot_menu_text.py` | 指令表整体替换（删旧 `/跑团记录`、`/角色` 行，加新指令） |
| `core/context.py` | `group_roles` 由 `pending.json` 取代；保留内存字典作为进程内缓存或直接移除（见下） |
| `webapp/static/trpg_records.js`、`trpg_record.js`、列表页文案 | 「群名」→「团名」 |
| `test/test_trpg_session.py` | 全部指令前缀更新 + 新增准备/校验用例 |
| `test/test_trpg_char.py` | 指令前缀更新 |
| `test/scripts/check_trpg_records_api.py` | 不变（只读记录目录） |
| `kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` | 指令表同步 |
| `CHANGELOG.md`、`core/config.py` | `[1.63.0]` + bump |

**关于 `core/context.py::group_roles`**：现在只有 `trpg_session` 用它（`.dm/.ob`），本次改为从 `pending.json` 读。为避免两套状态，`group_roles` 字典**移除**，所有读写走 `party.py`；`recording_sessions[...]["roles"]` 保留（录制期间的角色快照，来源于 `meta.json`）。

## 10. 失败路径

| 场景 | 行为 |
|---|---|
| `get_group_member_list` 超时/失败 | 拒绝开录，提示后端未响应，`强制开始` 可绕过 |
| `pending.json` 损坏 | 按空名单处理，记 warning，不阻塞准备 |
| `pending.json` 写入失败 | 记 `logger.exception`，回「保存准备状态失败」，内存状态不更新（避免显示成功） |
| 无角色卡的人执行 `/跑团 准备` | 回车卡链接，不写名单 |
| DM 退群后开录 | 视为"没有 DM"，提示重新 `.dm` |
| 群成员数很大（如 200 人） | 一次开录最多 200 次文件读 + 1 次 HTTP；大于 200 人时提示"成员过多，请使用强制开始"，避免长时间阻塞 |
| 已结束未导出的旧记录在升级后 | 无法再导出（`last_completed` 只在内存）；CHANGELOG 提示升级前先导出 |

## 11. 测试清单

| 层 | 文件 | 覆盖 |
|---|---|---|
| bot 进程内 | `test/test_trpg_session.py`（扩展） | AC01–AC07：指令路由、`.dm/.ob` 唯一性与持久化、准备/取消/卡片、四类校验失败与合并提示、`强制开始` 绕过、开录预置与 `pending.json` 清空、录制中拦截、文件损坏容错 |
| bot 进程内 | `test/test_trpg_char.py`（更新） | `/跑团 角色 …` 四个子命令；旧 `/角色 …` 不匹配 |
| webapp 独立进程 | `test/scripts/check_trpg_records_api.py`（保持） | 记录读取不受影响（回归确认） |
| 前端 DOM | `test/test_trpg_records_dom.js`（微调） | 「团名」文案 |
| 全量 | `python -m pytest -q` | AC08 |
| 真实环境 | 手工（AC09） | 进部署机冒烟，不进回归 |

## 12. 版本

新功能 minor：`BOTERO_VERSION` 1.62.0 → **1.63.0**。
