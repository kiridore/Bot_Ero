# 纯图片消息入档 — 验收记录

实施分支：`master`；版本 1.98.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 图片匹配 | `TestMatchDuringRecording::test_image_only_matches_while_recording` | 通过 |
| AC02 纯 @ 匹配 | `test_at_only_matches_while_recording` | 通过 |
| AC03 非录制不受影响 | `test_image_only_ignored_without_recording` | 通过 |
| AC04 指令不误判 | `test_unknown_party_command_still_ignored`（`/跑团 乱打` → False） | 通过 |
| AC05 端到端 | `test_dispatch_records_image_only_message`：`imgs/img_0001.jpg` 存在、`messages.jsonl` 1 条 | 通过 |
| AC06 全量回归 | `python -m pytest -q` → **959 passed**（5:16） | 通过 |
| AC07 文档与归档 | `openspec validate trpg-session-recording --strict` valid；`CHANGELOG [1.98.1]` 与 `BOTERO_VERSION = "1.98.1"` 一致；同一 commit 归档 | 通过 |

## 根因

```python
# 修复前
msg = self._first_text()
if not msg:
    return False        # ← 纯图片消息没有任何 text 段，直接被判「与我无关」
```

`main.py::plugin_pool` 只调用 `match()` 为 True 的插件的 `handle()`，所以入档函数从未执行。

## 修复后的实测（match → handle 真实顺序）

```
纯图片 match+handle: True   →  user [{'type': 'image', 'local': 'imgs/img_0001.jpg'}]
纯 at  match+handle: True   →  user [{'type': 'at', 'qq': '222'}]
纯文本 match+handle: True   →  user [{'type': 'text', 'text': '我推门'}]
```

## 为什么之前没被测出来

测试助手 `_run()` 直接调用 `handle()`，跳过了框架里的 `match()` 判定，所以「图片入档」的既有用例一直是通过的；新增的端到端用例显式先 `match()` 再 `handle()`，覆盖真实调度顺序。
