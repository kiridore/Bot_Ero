# 准备中卡片身份口径与整行可点 — 验收记录

实施分支：`master`；版本 1.79.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 身份口径 | `check_trpg_party_api.py`：本群 DM `is_dm=true can_audit=true`；普通用户 `is_dm=false can_audit=false`；超级用户非 DM `is_dm=false is_super=true can_audit=true` | 通过 |
| AC02 提示文案 | `test_trpg_party_render.js`：DM 卡含「你是本群 DM」；超级用户卡含「你是超级用户」且不含「你是本群 DM」；普通用户无「审核」字样 | 通过 |
| AC03 整行可点 | 同上：成员行为 `<a class="trpg-party-member is-link">` 且仍含「查看角色卡」；未准备成员输出「等待准备」 | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **779 passed**（4:53）；`openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.79.2]` 与 `BOTERO_VERSION = "1.79.2"` 一致 | 通过 |

## 实测与裁定

- **根因 1**：`is_dm = 本群 DM or 超级用户`，页面又用 `is_dm` 决定文案，于是超级用户在自己不是 DM 的群里被显示成 DM。实测确认：本群 DM 是 111、登录者是超级用户 999 时，接口返回 `is_dm=true`。
- **根因 2**：成员行只有行末按钮是 `<a>`，其余是文本，点击名字没有任何反馈。
- **权限不变**：`/api/trpg/party/<群>/card/<用户>` 的判定仍是「本人 / DM / 超级用户 → 允许；其他人按 `privacy.char_public`」，`can_audit` 只是把这个判定结果显式暴露给前端。
- **未做**：准备中卡片本身仍不是链接（没有对应的详情页）；如果你希望点卡片进到「本场准备详情」独立页面，需要单独设计。
