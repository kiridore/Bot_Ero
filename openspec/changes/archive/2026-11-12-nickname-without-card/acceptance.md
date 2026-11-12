# 取消群名片后昵称回落 — 验收记录

实施分支：`master`；版本 1.79.4。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 回落昵称 | `TestGroupCardNotice::test_empty_card_falls_back_to_nickname`：`card_new` 为空、`resolve_group_member_name` 返回「QQ昵称」→ `role_names` 更新 | 通过 |
| AC02 取不到时保留 | `test_empty_card_and_no_nickname_keeps_old`：查询返回空 → 保留「老名片」 | 通过 |
| AC03 无名片首次记录 | 实测 `_get_sender_nickname()`：`card=""` → 「QQ昵称」；`card` 与 `nickname` 皆空 → 「用户111」 | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **785 passed**（4:53）；`openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.79.4]` 与 `BOTERO_VERSION = "1.79.4"` 一致 | 通过 |

## 实测与裁定

- **问题边界**：`.dm` / `.ob` 首次记录**本就**会回落 QQ 昵称（`sender.card or sender.nickname`），所以「没设名片」不是问题；真正的缺口是「设过名片又取消」——`group_card` 通知只带一个空的 `card_new`，没有昵称可用。
- **回落实现**：新增 `resolve_group_member_name(group_id, user_id)`（`get_group_member_info`，3 秒超时，名片优先、其次昵称），只在空名片这一个事件上调用，不进入常规请求路径。
- **失败即保持**：接口不可用/返回空时保留旧昵称，不写盘、不报错，与 1.79.3 行为一致。
- **未验证**：LLOneBot 是否真的推送 `group_card`（同 1.79.3 的遗留前提）。
