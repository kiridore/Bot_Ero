# text-packs Specification

## Purpose
允许部署通过启动时加载的文案包覆盖内置提示，保留缺失或无效配置时的默认文案回退，避免为不同部署维护重复的业务代码。

## Requirements

### Requirement: 文案包加载与覆盖
系统 SHALL 支持bot.text_pack在启动时一次性加载文案覆盖，缺失或无效条目回退内置。菜单采用结构化条目覆盖，文字覆盖不得改变插件归属或权限；旧整段menu_text不得绕过有效菜单过滤。其他文案的现有覆盖和昵称替换规则保持。

#### Scenario: 未配置文案包
- **WHEN** bot.text_pack未配置或为空
- **THEN** 使用内置文案，菜单仍按当前位置有效插件过滤

#### Scenario: 包覆盖指定文案键
- **WHEN** 文案包为一个已声明的菜单条目提供合法文字
- **THEN** 用该文字及配置昵称渲染，但条目只有在所属插件和权限允许时才显示

#### Scenario: 旧整段菜单
- **WHEN** 包只提供旧menu_text整段覆盖
- **THEN** 启动警告格式需迁移，并采用可过滤的内置菜单，不因此拒绝启动或展示未授权指令

#### Scenario: 包缺键回落
- **WHEN** 缺少目标文案条目或其值为空/无效
- **THEN** 使用对应内置默认，其他合法覆盖不受影响

### Requirement: 坏包降级不崩溃

文案包路径不存在、yaml 语法错误或顶层不是映射时，系统 SHALL 记 WARNING 日志并回落全部内置文案，进程正常启动运行。

#### Scenario: 包文件缺失

- **WHEN** `bot.text_pack` 指向不存在的文件
- **THEN** 启动记 WARNING，`get_text` 全部返回内置默认，无未捕获异常
