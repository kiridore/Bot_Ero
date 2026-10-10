# 注册插件与私聊准入（M1 · 三提案之一）

## Why

公开实例的私聊入口需要对陌生账号做最基本的身份登记：知道谁在用、给过一次《用户协议》、并让新用户从一个最小功能集开始（配合逐步开放运营）。所有者已通过三轮质询定稿完整流程（2026-10-10，见 design.md 共识记录）。

## What Changes

1. **新插件 `plugins/register/`**：`/注册` 与 `/同意EULA` 两条指令（大小写不敏感），承载注册会话流程：分段文案（按定稿原样，含 `*写写*` 星号）→ 合并转发《用户协议》→ 等待同意 → 写入 `user_accounts`（新增 `eula_version`、`agreed_at` 两列，幂等迁移）→ 为账号播种 `register.default_pack` 功能包 → 发布"注册完成"内部通知 → 收尾文案。
2. **私聊准入检查**（`register.require`，缺省 false）：开启后未注册账号的私聊消息只放行 `register` 与菜单插件；命令样式的其他指令回一次限频提醒（`register.reminder_minutes`，缺省 30）。关闭时零行为变化（私有版现状）。
3. **welcome 插件文案键**：好友欢迎消息改经文案包键 `welcome.friend_add`（内置默认 = 现有私有文案，逐字节不变）；公开部署由 `community.yaml` 覆盖为中性引导文案。
4. **资料卡通知**：`personal_records` 插件订阅"注册完成"，对新账号生成资料卡（新用户全零卡）；该插件未开放时静默跳过，收尾文案照常。
5. **配置节 `register:`**：`require` / `eula_file` / `default_pack` / `reminder_minutes`；启动校验：require 开启时协议文件必须存在可读，default_pack 必须是已定义功能包。
6. **菜单**：条目表新增 `/注册` 行（`/同意EULA` 为流程内部指令，不进菜单）。
7. **EULA 草稿**：`docs/eula/v1.md`，文件头标注草稿，所有者定稿后生效。

## Scope / Non-Goals

- 不做群审核、黑名单、频控执行（后续两个提案）。
- 不做协议改版的重新同意策略（挂起：协议版本号已记录，策略另议）。
- 不改 `auto_friend`（自动通过好友申请，两部署相同）。
- 不做逐字打字动画（停顿为段间 sleep）。
- 私有部署 `require` 缺省 false，全部行为不变。

## Capabilities

### New Capabilities
- `community-registration`：注册会话流程、同意记录持久化、播种、私聊准入与提醒的完整契约。

### Modified Capabilities
- `text-packs`：新增 `welcome.friend_add` 键（内置默认不变）。

## Impact

- 代码：新 `plugins/register/`、`main.py`（私聊准入）、`core/config.py`（register 节与校验）、`core/context.py`（启动校验补 default_pack/eula）、`core/db/_base.py`（user_accounts 加列迁移）、`plugins/welcome/`（文案键）、`plugins/personal_records/`（订阅注册完成）、`plugins/menu/entries.py`（新行）。
- 数据：`user_accounts` 加两列（幂等 ALTER）；内存会话字典重启即失（安全侧：未同意视为未同意）。
- 公开模板：`allowed_plugins`/`system_plugins` 增加 `register`；`community.yaml` 增欢迎键。
- 用户可见（公开部署）→ bump **1.53.0**，CHANGELOG 同步；私有部署无可见变化。

## 验收标准

| 编号 | 验证命令 | 必须通过 |
|---|---|---|
| AC1 | `python -m pytest test/test_register_flow.py -q` | 全流程（分段文案逐句、停顿、合并转发结构、大小写不敏感同意、持久化、播种、通知）；未注册限制与 30 分钟限频提醒；群聊提示；重复 /注册 重发；已注册 /同意EULA 回执；重启后从协议步重来 |
| AC2 | `python -m pytest test/test_register_gate.py -q` | require=false 时全部现状（未注册也可用全部指令）；require=true 未注册仅 register+菜单放行；已注册零影响；群消息不受影响 |
| AC3 | `python -m pytest test/test_config_validation.py test/test_deployment_templates.py -q` | register 节类型校验；require 开启时协议文件缺失/包名不存在启动失败；公开模板加载通过且含 register |
| AC4 | `python -m pytest test/test_enabled_menu.py -q` | /注册 进菜单条目；未注册快照下菜单只显示注册与菜单相关行；/同意EULA 不在菜单 |
| AC5 | `python -m pytest test/test_community_db.py -q` | user_accounts 加列迁移幂等；eula_version/agreed_at 读写 |
| AC6 | `python -m pytest -q` | 全量回归通过 |
| AC7 | `openspec validate community-registration --strict`；`git -c core.whitespace=cr-at-eol diff --check` | 校验通过；kb/PLUGIN_CATALOG、QUICK_REFERENCE、菜单、CHANGELOG、版本 1.53.0 一致 |

## 维护者可持续性影响

注册是一次性自助流程，无新增人工响应；EULA 独立文件由所有者维护；新用户从最小功能集开始，降低首批支持面。提醒限频防止未注册用户被消息骚扰、也防止机器人被刷。
