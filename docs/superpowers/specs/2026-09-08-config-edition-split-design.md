# 配置分侧与 edition 引入（T0.1）— 设计文档

- 日期：2026-09-08
- 状态：设计已与所有者确认（D5 主干共存细则、D11 群自治不开放均已拍板；本 spec 为其配置层落地）
- 前序：`docs/community/community-edition-plan.md`（决策记录 D1-D11）、`specs/conventions.md` §双形态接缝（edition 接缝白名单）
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-09-08-config-edition-split.md`

## 背景与决策

社区版与私有版**同一主干 + `bot.edition` 配置切换**（D5）。社区形态是纯 bot 部署（D6）：不跑 webapp、无默认群（多群公共服务）、无 OneBot HTTP 昵称解析、无时间线上报。而现行 `core/config.py` import 时对**全部**部署统一校验必填键（含 `bot.default_group`、`onebot.http_url`、`timeline.url/token`），社区形态根本无法启动——T0.1 解除这一阻塞，并产出后续任务（T0.2-T0.4、T1.2、T1.4、T1.5）消费的形态常量。

| # | 决策 |
|---|------|
| P1 | `bot.edition: private\|community`，**缺省 `private`**；非法值启动即退出（提示可选值）。私有部署零行为变化是硬约束 |
| P2 | 必填键拆两组：`_REQUIRED_BOT`（两形态共有：bot 基础 7 键 + `auth.salt`）+ `_REQUIRED_PRIVATE_EXTRA`（`bot.default_group`、`onebot.http_url/token`、`timeline.url/token`）；community 只校验前者 |
| P3 | 新模块级常量（edition 差异**全部收在 config.py 接缝内**，消费方零分支）：`EDITION: str`、`SYSTEM_PLUGINS_CONF: list[str]`（缺省 `[]`，T0.4 消费）、`COMMUNITY_MAX_GROUPS: int`（缺省 50，T1.4 消费）、`COMMUNITY_CMD_COOLDOWN_SECONDS: int`（缺省 community=3 / private=0 即关闭；显式配置不分形态生效，T1.5 消费） |
| P4 | `DEFAULT_GROUP_ID` 放宽为 `int \| None`（community 缺省 None，`GROUP_ID` 别名跟随）；`TIMELINE_URL/TOKEN`、`ONEBOT_HTTP_URL/TOKEN` 改宽松读取（缺节/缺键 → `""`，不 KeyError）。`None`/`""` 的**消费方语义改动不在本任务**：发送兜底属 T0.2，上报 no-op 属 T0.3——本任务只做配置层，私有形态下这些值仍必填且为真值 |
| P5 | `config.example.yaml` 标注各键形态适用性并补 `community` 节示例；`kb/QUICK_REFERENCE.md` 配置键表同步（含必填列改"私有✅"） |
| P6 | 内部基础设施变更：CHANGELOG 记 `[未发布]` **不 bump** `BOTERO_VERSION`；T0.1 全部改动**一个逻辑 commit**（`feat(配置): bot.edition 部署形态与必填键分侧`） |

## 非目标

- 不改 `core/api.py`（DEFAULT_GROUP fallback）、`core/timeline_client.py`（no-op）——分别属 T0.2/T0.3，本任务后社区形态仍不可完整冷启动属预期
- 不产出 `config.example.community.yaml` 完整模板（T1.7）
- 不动 `SYSTEM_PLUGINS` 常量本体（`core/context.py`，T0.4 才消费 `SYSTEM_PLUGINS_CONF`）
- 不做配置热重载、不做多实例合并配置（YAGNI）

## ① 校验规则（`_load`）

1. 文件不存在 → 退出并提示 `cp config.example.yaml config.yaml`（现状不变）
2. `edition = (bot.edition or "private")`，值 ∉ {private, community} → 退出，消息含 `bot.edition` 与可选值
3. 按 edition 选必填组，逐点路径校验（None/""/[] 均算缺失，现状语义不变）

## ② 常量与消费方对照

| 常量 | 类型 | 缺省 | 消费方 |
|---|---|---|---|
| `EDITION` | `str` | `"private"` | T0.4（系统插件）、T0.7（功能包）、T1.2（门控）、T1.6（权限点） |
| `SYSTEM_PLUGINS_CONF` | `list[str]` | `[]`（= 用内置集合） | T0.4 |
| `COMMUNITY_MAX_GROUPS` | `int` | `50` | T1.4（入群审核超限拒绝） |
| `COMMUNITY_CMD_COOLDOWN_SECONDS` | `int` | community 3 / private 0 | T1.5（CommandPlugin 频控） |
| `DEFAULT_GROUP_ID`（`GROUP_ID` 别名） | `int \| None` | community `None` | T0.2（api.py 三处兜底）、webapp 周报（私有形态恒 int） |
| `TIMELINE_URL` / `TIMELINE_TOKEN` | `str` | `""` = 上报关闭 | T0.3（timeline_client no-op） |
| `ONEBOT_HTTP_URL` / `ONEBOT_TOKEN` | `str` | `""` | webapp 昵称解析（私有形态必填真值；社区形态无消费方） |

## ③ 边界

- community 最小配置 = bot 基础 7 键 + `auth.salt`（`edition` 可缺省），其余节全部可省
- `system_plugins` 键列表元素转 str；空列表与缺省等价
- `cmd_cooldown_seconds: 0` 显式配置 → 两形态都关闭频控（0 是合法显式值，与"缺省"区分：缺省才按形态取 3/0）

## ④ 测试（`test/test_config_loader.py` 既有模式：临时目录 + `BOTERO_CONFIG` + `importlib.reload`，`finally` 恢复 conftest 配置）

- 社区最小配置 `_load` 通过（缺 default_group/onebot/timeline 不退出）
- 私有形态缺 `bot.default_group` → SystemExit 且消息含键名
- 非法 `bot.edition` → SystemExit 且消息含 `bot.edition`
- 社区形态常量：`EDITION`/`DEFAULT_GROUP_ID is None`/`TIMELINE_URL == ""`/`SYSTEM_PLUGINS_CONF == []`/`COMMUNITY_*` 缺省值
- 私有形态：无 edition 键 → `"private"`；`system_plugins`/`community` 覆盖生效
- 全量 `pytest` 全绿（既有用例不改一字）

## ⑤ 文档与版本（同 commit）

- CHANGELOG `[未发布]`（不 bump）；`config.example.yaml` 标注；`kb/QUICK_REFERENCE.md` 键表
- `docs/community/development-plan.md` §T0.1 勾选进度
