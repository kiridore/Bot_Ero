# 设计：规则选择、COC 恢复与网页行式条目

## 1. 已确认决策

| 编号 | 决策 | 来源 |
|---|---|---|
| D1 | 网页记录改为行式条目（每场一行），保留「只看我参加的」开关与消息条数 | Q1 A / Q5 A |
| D2 | 规则做**真实切换**：恢复 COC 7th 检定与奖惩骰 | Q2 C / Q6 B |
| D3 | 「我的身份」按登录用户计算：DM / 观察者 / 角色卡名（玩家）/ 玩家 / 未参与；不额外展示本团 DM | Q3 A |
| D4 | 人数只统计普通玩家（排除 DM、观察者、机器人） | Q4 C |
| D5 | 规则由当前 DM（或超级用户）设置 | Q7 A |
| D6 | 规则存 `pending.json.rules`，开录写进 `meta.json` 并随准备状态清空 | Q8 A |
| D7 | `/跑团 规则` 无参列出、带参设置，录制中拒绝 | Q9 |
| D8 | COC 三种入口全恢复：`.ra`、`.r c<值>`、`.rh c<值>` | Q10 A |
| D9 | 奖惩骰恢复后缀写法（并同时接受 `.r 1d100b2`） | Q11 A |
| D10 | 规则不匹配时拒绝并提示切换方法 | Q12 A |
| D11 | COC 检定只接受数值 | 实施裁定 |

## 2. 规则注册表（`core/trpg/game_systems.py`）

```python
DEFAULT_RULE = "dnd5e"
GAME_SYSTEMS = {
    "dnd5e": {"name": "DND 5E", "check_cmd": ".rc", "check_handler": "_handle_dnd_check",
              "check_usage": "...", "aliases": ("dnd", "5e", "dnd5e", "dnd5th")},
    "coc7th": {"name": "COC 7th", "check_cmd": ".ra", "check_handler": "_handle_coc_check",
               "check_usage": ".ra <技能值>", "aliases": ("coc", "coc7", "coc7th", "7th")},
}
rule_name(rule_id) -> str      # 未知 id 原样返回
normalize_rule(text) -> str|None
```

`plugins/trpg_dice/games.py` 只做重导出，保证骰子与网页读同一份注册表。

## 3. 规则存储与生效

```
pending.json.rules   ← /跑团 规则 写入；未设置时默认 dnd5e（读时补默认，不强制重写）
session["rules"]     ← 开录时取 pending，写入 meta.rules 与内存会话
meta.json.rules      ← 记录的事实来源；重启续录时回填 session["rules"]
```

`core/trpg/party.py::current_rule(group_id)`：
```python
session = runtime_context.get_recording_session(group_id)
if session: return session.get("rules") or DEFAULT_RULE
return read_pending(group_id)["rules"] if group_id is not None else DEFAULT_RULE
```

骰子插件每回合调用它，所以"开录后 pending.json 被清空"不会让本场规则回落到默认值。

## 4. COC 7th 指令与判定

| 入口 | 说明 |
|---|---|
| `.ra 70` | 技能检定，输出 `D100=<roll> [技能=70] → <成功等级>` |
| `.r c70` | 同 `.ra` |
| `.rh c70` | 暗骰版：群内只说「悄悄掷出骰子」，结果回私聊并作为暗骰入档 |
| `.r b2` / `.r 1d100b2` | 奖励骰（1–10 颗） |
| `.r p1` / `.r 1d100p1` | 惩罚骰（1–10 颗） |

成功等级（`rolls.py::coc_check`，与历史实现一致）：`roll <= 技能/5` 极限成功；`<= 技能/2` 困难成功；`<= 技能` 常规成功；`>= 96` 大失败；否则失败。技能值须在 1–100。

奖惩骰沿用历史算法：基础 D100 与 N 颗个位骰组成候选，奖励取个位最大、惩罚取最小，超过 100 视为 100。

## 5. 规则门控

- 当前规则为 `dnd5e`：`.ra`、`.r b/p` 输出「当前规则是 DND 5E，…请先由 DM 发送 `/跑团 规则 coc7th`」。
- 当前规则为 `coc7th`：`.rc` 输出「当前规则是 COC 7th，属性检定请用 `.ra <技能值>`」。
- `.r` 通用掷骰、`.rh` 通用暗骰两种规则下都可用。

## 6. 网页接口

列表 `GET /api/trpg/records` 每条新增：

| 字段 | 来源 |
|---|---|
| `rules` / `rules_name` | `meta.rules` → `game_systems.rule_name()`；缺字段时 `""` / 「未知规则」 |
| `player_count` | `participants` 中 `role` 为空的条目数 |
| `my_role` | `{role: "dm"|"ob"|"player"|"", char_name}` |

详情 `GET /api/trpg/records/{群号}/{目录}` 新增 `rules` / `rules_name`。

## 7. 前端

- 列表（`trpg_records.js`）：`.trpg-row` 一行一条，标题行团名 + 状态徽标，细节行 `起止时间 · N 人 · 我的身份 · 规则 · N 条消息`；未结束时时间显示为 `开始 — 进行中`。
- 详情（`trpg_record.js`）：头部 meta 行追加规则名。
- 样式：`.trpg-card` 系列换成 `.trpg-row` 系列，删除不再使用的 `.trpg-badge.is-exported`，沿用 `:root` token。

## 8. 失败路径

| 场景 | 行为 |
|---|---|
| `pending.json` 缺 `rules` 或类型不对 | 按默认 `dnd5e` 读，不写盘 |
| 规则写入失败 | 回「保存规则失败」，不改内存 |
| `meta.json` 缺 `rules`（旧记录） | 网页显示「未知规则」；续录时 session 用默认规则 |
| COC 技能值越界 | `ValueError`，回「技能值应在1~100之间」 |
| 奖惩骰数量越界 | 回「奖励骰最多 10 颗」/「惩罚骰最多 10 颗」 |

## 9. 影响面

| 文件 | 改动 |
|---|---|
| `core/trpg/game_systems.py`（新） | 规则注册表与 normalize/name |
| `core/trpg/party.py` | `rules` 默认值、`set_rule`、`current_rule` |
| `plugins/trpg_dice/__init__.py` | `.ra` 路由、`c<值>`、奖惩骰、规则门控 |
| `plugins/trpg_dice/rolls.py`（新） | COC 检定与奖惩骰算法（从 git 历史恢复） |
| `plugins/trpg_dice/games.py` | 改为重导出 |
| `plugins/trpg_session/__init__.py` | `/跑团 规则`、开录写 `meta.rules`、续录恢复规则 |
| `webapp/trpg/app.py` | 列表/详情新字段、`_my_role` |
| `webapp/static/trpg_records.js` / `trpg_record.js` / `trpg.css` | 行式条目与规则展示 |
| `plugins/menu/bot_menu_text.py` 与 docs | 指令表同步 |
| 测试 | `test_trpg.py`、`test_trpg_session.py`、`check_trpg_records_api.py`、新增 `test_trpg_records_list_dom.js` |

## 10. 测试清单

| 层 | 文件 | 覆盖 |
|---|---|---|
| 骰子 | `test/test_trpg.py` | AC01、AC04–AC06 |
| 会话 | `test/test_trpg_session.py` | AC02、AC03 |
| webapp | `test/scripts/check_trpg_records_api.py` | AC07 接口字段 |
| 前端 | `test/test_trpg_records_list_dom.js`（新）、`test/test_trpg_records_dom.js` | AC07 列表、AC08 详情 |
| 全量 | `python -m pytest -q` | AC09 |
