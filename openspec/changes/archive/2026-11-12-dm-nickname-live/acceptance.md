# 群名片实时刷新昵称 — 验收记录

实施分支：`master`；版本 1.79.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 DM 名片 | `TestGroupCardNotice::test_updates_dm_nickname`：`.dm` 后收到 `card_new="新名片"`，`role_names["111"] == "新名片"` | 通过 |
| AC02 观察者名片 | `test_updates_observer_nickname`：`.ob` 用户同样被更新 | 通过 |
| AC03 无角色用户 | `test_ignores_member_without_role`：路人改名片后 `pending.json` 仍不存在 | 通过 |
| AC04 空名片 | `test_ignores_empty_card`：保留原昵称 | 通过 |
| AC05 其它通知 | `test_other_notice_not_matched`：`group_recall` 不匹配本插件 | 通过 |
| AC06 文档与归档 | 全量 `pytest` → **784 passed**（4:54）；`openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.79.3]` 与 `BOTERO_VERSION = "1.79.3"` 一致 | 通过 |

## 实测与裁定

- **写盘边界**：只有「该用户已在 `roles` 里有 DM/观察者标记」才写，避免群里任意成员改名都去创建 `pending.json`；名字没变、`card_new` 为空、群号缺失时一律不写。
- **事件选择**：走 OneBot `group_card` 通知（`card_new` 字段）而不是定时拉群成员列表——零延迟、零额外请求。
- **未验证**：LLOneBot 是否真的推送 `group_card`。不推送时本逻辑不会执行，行为与 1.79.2 完全一致、不会报错；部署后可让 DM 改一次名片看是否生效。
- **未做**：记录 `meta.participants[].nickname` 不做同步（每条消息自带当时的昵称，快照本来就是历史值）。
