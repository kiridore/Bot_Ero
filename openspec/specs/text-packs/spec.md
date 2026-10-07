# text-packs Specification

## Purpose
允许部署通过启动时加载的文案包覆盖内置提示，保留缺失或无效配置时的默认文案回退，避免为不同部署维护重复的业务代码。

## Requirements

### Requirement: 文案包加载与覆盖

系统 SHALL 支持 `bot.text_pack` 配置指向一个 yaml 文案包：包内与文案键同名的条目覆盖内置默认文案，缺键、空值或未配置该键时使用内置默认。加载在进程启动时一次性完成。

#### Scenario: 未配置文案包

- **WHEN** `bot.text_pack` 未配置或为空
- **THEN** 所有文案取内置默认，行为与引入本机制前完全一致

#### Scenario: 包覆盖指定文案键

- **WHEN** 包内 `menu_text` 为非空字符串且已配置加载该包
- **THEN** 菜单文案返回包文本，文本中的 `{NICKNAME}` 占位符被替换为配置昵称

#### Scenario: 包缺键回落

- **WHEN** 包存在但不含目标键，或其值为空串/null/非字符串
- **THEN** 返回该键的内置默认文案

### Requirement: 坏包降级不崩溃

文案包路径不存在、yaml 语法错误或顶层不是映射时，系统 SHALL 记 WARNING 日志并回落全部内置文案，进程正常启动运行。

#### Scenario: 包文件缺失

- **WHEN** `bot.text_pack` 指向不存在的文件
- **THEN** 启动记 WARNING，`get_text` 全部返回内置默认，无未捕获异常
