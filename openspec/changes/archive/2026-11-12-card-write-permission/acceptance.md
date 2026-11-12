# 角色卡写入失败提示 — 验收记录

实施分支：`master`；版本 1.82.5。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 写入层 | `TestWriteJsonOSError`：PermissionError → ValueError，含「角色卡写入失败」「Permission denied」与目录路径 | 通过 |
| AC02 指令层 | `TestWriteFailureMessage`：`.hp -1` 回复含写入失败原因 | 通过 |
| AC03 全量回归 | 全量 `pytest` → **858 passed**（5:17） | 通过 |
| AC04 文档与归档 | `openspec validate trpg-vitals --strict` valid；`CHANGELOG [1.82.5]` 与 `BOTERO_VERSION = "1.82.5"` 一致 | 通过 |

## 生产事故结论

- **现象**：`.hp 满` 回「指令处理出错，请检查格式」。
- **根因**：webapp 进程创建的 `server_data/trpg_chars/<用户>/` 目录，bot 进程无写权限；`_write_json` 建临时文件抛 `PermissionError`，被插件兜底成通用文案。
- **代码侧**（本变更）：错误消息透出原因与路径，下次一眼定位。
- **部署侧**（需运维执行）：确认两进程运行用户；统一用户或共享组 + 组写 + setgid。受影响指令：`.hp/.san/.mp/.sc`、`.ra` 成长标记、`/跑团 成长`、`/跑团 角色 切换`（后三者本就有自己的失败提示）。
