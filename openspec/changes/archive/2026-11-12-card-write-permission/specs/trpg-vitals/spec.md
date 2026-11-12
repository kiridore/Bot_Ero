# trpg-vitals — 变更（写入失败提示）

## ADDED Requirements

### Requirement: 写入失败透出原因
角色卡写入因 `OSError`（权限、磁盘等）失败时，`character_store` SHALL 记录错误日志并抛出含原因与目录路径的 `ValueError`；数值指令（`.hp/.san/.mp/.sc`）SHALL 把该消息原样回复给用户，MUST NOT 显示与写入无关的兜底文案（如「指令处理出错，请检查格式」）。

#### Scenario: 目录无权限
- **WHEN** bot 进程对 `server_data/trpg_chars/<用户>/` 无写权限时发送 `.hp -1`
- **THEN** 回复包含「角色卡写入失败：Permission denied」与该目录路径，日志记录完整异常
