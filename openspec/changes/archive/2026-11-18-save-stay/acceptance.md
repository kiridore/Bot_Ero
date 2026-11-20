# 保存后留在编辑页 — 验收记录

实施分支：`master`；版本 2.1.5。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 保存后留在编辑页 | `node test/test_trpg_coc_save_stay.js`：「保存后留在编辑页」「不再直接跳列表」 | 通过 |
| AC02 提示与清理 | 同上：「识别 saved=1」「提示可以应用年龄调整」「提示后清理地址栏」 | 通过 |
| AC03 showToast 可用 | 同上：「本页定义了 showToast」「调用点仍然存在（13）」「showToast 可执行 / 写入文字并显示 / 错误态带 error 类」 | 通过 |
| AC04 页面承载 | 同上：「页面有 #toast 容器」「样式定义 .toast」 | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **1012 passed**（5:42）；DOM 套件 34 个全过（含新用例） | 通过 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [2.1.5]` 与 `BOTERO_VERSION = "2.1.5"` 一致；同一 commit 归档 | 通过 |

## 顺带修掉的隐藏缺陷

`trpg_coc.js` 里 12 处 `showToast(...)` 此前全部无效（本页未定义该函数）：

| 位置 | 原本该提示 |
|---|---|
| `fillRequiredSkills` 之后 | 已补入本职技能 N 项 |
| 资产「按规则填入」 | 已按「标准」填入参考值 / 查询失败 / 先选择币种 |
| `sendAgeAdjust` | 年龄调整已应用 / 已记录：不再提示 / 失败原因 |
| `undoAgeAdjust` | 已撤销年龄调整 / 撤销失败 |
| `save` | 职业名不在列表里 |
| 清除职业点 | 已清除职业点：xxx |

修前这些操作要么静默、要么（`sendAgeAdjust` 的 catch 里）再抛一次 `ReferenceError`，导致失败原因不可见。
