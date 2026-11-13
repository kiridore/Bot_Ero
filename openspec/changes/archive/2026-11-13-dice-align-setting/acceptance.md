# 骰子结果对齐设置 — 验收记录

实施分支：`master`；版本 1.91.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 三种样式 | 「三种对齐都有样式规则」「气泡文字对齐随容器类变化」 | 通过 |
| AC02 默认居中 | 「默认居中」「默认按钮图标为居中」「按钮标签写明当前对齐」 | 通过 |
| AC03 循环切换 | 「点一下右对齐」「右对齐写入 localStorage」「再点回到左对齐」「第三次点回居中」 | 通过 |
| AC04 非法值 | 「非法存档回落居中」 | 通过 |
| AC05 页面元素 | 「页面有对齐按钮」 | 通过 |
| AC06 全量回归 | `python -m pytest -q` → **925 passed**（5:01）；详情 DOM 115 项全过 | 通过 |
| AC07 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.91.0]` 与 `BOTERO_VERSION = "1.91.0"` 一致；同一 commit 归档 | 通过 |

## 实现说明

- 对齐由消息容器的 `dice-left|dice-center|dice-right` 类驱动，`.trpg-msg.is-bot` 自身不再写死 `align-self`，避免两处规则打架（本轮顺带清掉了两条重复的 `align-items` 规则）。
- 按钮图标用自托管 lucide 的 `align-*` 三条 path，无外链。
- 存档键 `botero_trpg_dice_align`；`localStorage` 不可用时仅本次生效。
- 默认值写回存档，保证「没设置过」和「显式居中」表现一致。

## 顺带修掉的测试环境问题

本机 shell 设了进程级 `HTTP_PROXY`/`HTTPS_PROXY`，`check_web_checkin_timeline.py` 里对 `127.0.0.1` 的 `urlopen` 被代理劫持，报「服务器起不来」的假失败（全量跑时 6 failed）。`test/scripts/_env.py` 现在把 `127.0.0.1,localhost` 写进 `no_proxy`/`NO_PROXY`，脚本无需外部改动即可通过。
