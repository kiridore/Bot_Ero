# 准备名单与 DM 审核 — 验收记录

实施分支：`master`；版本 1.78.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 准备中列表 | `check_trpg_party_api.py`：列表含本群、成员含 DM 与已准备玩家、`已准备 1/3`、规则名下发、DM 视角 `is_dm=true`、陌生人视角 `is_dm=false` | 通过 |
| AC02 无 DM 不列出 | 把唯一 DM 改成观察者后 `/api/trpg/parties` 返回空列表 | 通过 |
| AC03 审核权限 | DM 可看参与者卡；本人可看自己；私密卡对旁观者 403；私密卡 DM 仍 200；公开卡旁观者 200 | 通过 |
| AC04 越界拒绝 | 名单外用户 404；没有准备的群 404 | 通过 |
| AC05 页面渲染 | `test_trpg_party_render.js`：群号/规则/`已准备 1/2`、DM 审核提示、`/trpg/char/222/3?party=296470819` 链接、未准备「等待准备」、观察者徽标、空角色名「未选角色卡」 | 通过 |
| AC06 查看页门 | `char_view.js` 在 `?party=` 时请求 `/api/trpg/party/<群>/card/<用户>`；无参数时保持 `/api/characters/...` | 代码层通过，浏览器手测待确认 |
| AC07 文档与归档 | 全量 `pytest` → **766 passed**（4:52）；`openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.78.0]` 与 `BOTERO_VERSION = "1.78.0"` 一致 | 通过 |

## 实测与裁定

- **数据来源**：只读 `pending.json`（`roles` + `prepared`），不新增存储；`char_id` 来自 1.63 的准备快照，因此名单能直接链到具体角色卡。
- **权限分层**：本人 → 放行；本群 DM / 超管 → 放行且不受隐私限制；其他人 → 按 `privacy.char_public`。范围锁在「该群 + 名单内」，离开名单即 404。
- **生命周期**：列表只显示「有 DM 且未开录」的群；开录后 `pending.json` 被删除，该群自动从准备中区块消失，转为记录列表。
- **已知限制**：DM 与观察者在名单里显示 QQ 号——`pending.json` 的 `roles` 只存 ID，没有昵称；若要显示昵称需要扩展存储结构（未做）。
