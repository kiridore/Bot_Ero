# trpg-rule-selection Specification

## Purpose
每个群可以选择自己使用哪套跑团规则：`/跑团 规则` 列出当前规则与可选项，DM（或超级用户）带参切换。选择存进准备状态 `pending.json`，开录时写进记录的 `meta.json.rules` 并在录制期间固定，重启续录后从记录恢复。规则同时决定骰子插件接受哪套检定指令。

## Requirements

### Requirement: 规则注册表
系统 SHALL 在一处维护规则注册表（`core/trpg/game_systems.py`），每项含规则 id、展示名、检定指令、处理器名与大小写别名；至少包含 `dnd5e`（DND 5E）与 `coc7th`（COC 7th）。骰子插件与网页 MUST 读取同一份注册表，MUST NOT 各自硬编码规则名。未知规则 id SHALL 原样作为展示名返回，供旧记录显示。

#### Scenario: 大小写与别名
- **WHEN** 用户输入 `/跑团 规则 COC7th` 或 `/跑团 规则 coc7` 或 `/跑团 规则 coc`
- **THEN** 一律识别为 `coc7th`

#### Scenario: 未知规则
- **WHEN** 用户输入 `/跑团 规则 gurps`
- **THEN** 机器人提示未知规则并列出可用规则，不写入任何状态

### Requirement: 规则查看与切换
`/跑团 规则` SHALL 输出当前规则展示名与可选项（含各自的设置方式）。`/跑团 规则 <规则名>` SHALL 仅允许当前 DM 或超级用户执行，成功时把规则 id 写入本群 `pending.json` 的 `rules` 字段并回执新规则名。录制期间（`recording_sessions` 含该群）两种子命令 MUST 被拒绝并提示先结束录制。非 DM 执行切换 SHALL 被拒绝且不写入。

#### Scenario: 查看当前规则
- **WHEN** 群成员发送 `/跑团 规则`
- **THEN** 机器人回复当前规则展示名与可选项

#### Scenario: DM 切换规则
- **WHEN** DM 发送 `/跑团 规则 coc7th`
- **THEN** `pending.json.rules` 变为 `coc7th`，回执包含「COC 7th」

#### Scenario: 非 DM 切换
- **WHEN** 非 DM 且非超级用户发送 `/跑团 规则 coc7th`
- **THEN** 机器人拒绝，`pending.json.rules` 不变

#### Scenario: 录制中
- **WHEN** 该群正在录制时发送 `/跑团 规则` 或 `/跑团 规则 dnd5e`
- **THEN** 机器人拒绝并提示录制中无法修改规则

### Requirement: 规则的存储与生效
规则 SHALL 存于 `<python_data_path>/trpg_records/<群号>/pending.json` 的 `rules` 字段，与准备名单共用同一文件与原子写；缺字段或类型不正确时 SHALL 按默认规则 `dnd5e` 处理且不强制重写文件。开始录制时 SHALL 把当时生效的规则写入 `meta.json.rules` 并保留在录制会话中；录制期间 `current_rule()` SHALL 优先取会话里的规则，未录制时取 `pending.json`，都没有时返回默认规则。重启续录时 SHALL 从 `meta.json.rules` 恢复会话规则。

#### Scenario: 开录写入
- **WHEN** 本群规则为 `coc7th` 时开始录制
- **THEN** 记录 `meta.json.rules` 为 `coc7th`，录制中骰子按 COC 规则工作（即使 `pending.json` 已被清空）

#### Scenario: 旧文件与旧记录
- **WHEN** `pending.json` 没有 `rules` 字段，或记录 `meta.json` 没有 `rules` 字段
- **THEN** 前者按 `dnd5e` 处理；后者续录时会话使用默认规则，网页显示「未知规则」
