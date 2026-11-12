# 撤销 CQ 码字符串格式支持 — 验收记录

实施分支：`master`；版本 1.82.4。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 撤销完整 | `git diff f326378 HEAD -- core/ plugins/ webapp/ test/` 为空（除版本号/CHANGELOG/OpenSpec/规格文档外无差异） | 通过 |
| AC02 at 路径仍在 | `test_trpg_vitals.py` 27 例全过（at 段 / 纯文本 @ / 无空格 @ / null 值 / 未设当前卡） | 通过 |
| AC03 全量回归 | 全量 `pytest` 全绿 | 通过 |
| AC04 文档与归档 | `openspec validate --strict` valid；`CHANGELOG [1.82.4]` 与 `BOTERO_VERSION = "1.82.4"` 一致；归档与实现同一 commit | 通过 |

## 裁定

- **为什么版本不回退到 1.82.2**：私有部署按 master HEAD 拉取，版本需单调；撤销以 1.82.4 记录。
- **保留物**：1.82.2 全部修复（at 段识别本来就在、纯文本 `@QQ号` 兜底、null 当前值兜底、未设当前卡提示）不受影响。
