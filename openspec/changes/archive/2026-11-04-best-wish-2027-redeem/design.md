# 设计

## 决策与理由

1. **格式放宽为每段 `[A-Z0-9]{4}`**：`BEST-WISH-2027` 仅第三段需要数字，但按段统一放宽（三段同规则）比「仅末段允许数字」简单且不缩小任何现有码的合法空间；输入仍先 `.strip().upper()` 归一，小写输入行为不变。前端 placeholder `XXXX-XXXX-XXXX` 仍合法，不动。
2. **一个回调解锁三个称号（同事务）**：沿用注册表回调契约 `callback(db, user_id) -> str`，`db.titles.unlock(..., commit=False)` 连调三次；既有原子性要求保证不会出现「部分解锁」。不新增积分奖励（所有者未要求）。
3. **三称号稀有度全部 `rare`**（所有者 Q1 裁定）：介于测试员与 1st 之间，周边赠品定位。
4. **提示桩插件形态**：重建 `plugins/redeem_code/__init__.py`，继承 `CommandPlugin`，`COMMANDS = ("/兑换码", "/兌換碼")`（与旧插件一致的繁体别名）。`handle`：先 `self.api.delete_msg(self.bot_event.message_id)`（尽力而为，返回值仅记录日志），随后无条件 `send_msg(at(user_id), text(提示语))`（所有者 Q2=A：撤回失败仍提示）。私聊中撤回自然失败，提示照常送达私聊。插件不 import 数据库层、无状态。
5. **提示文案**：「兑换码功能已迁移至网页个人主页「兑换码」页签」（所有者 Q3=A，与菜单第 39 行措辞对齐）。
6. **菜单文本不改**：既有行「兑换码请在网页个人主页「兑换码」页签使用」已正确描述现状；提示桩是引导措施而非功能指令，不新增菜单行。
7. **插件目录与目录文档**：插件以原名 `redeem_code` 回归（编号 45 复用，`kb/PLUGIN_CATALOG.md` 头部计数 46→47，注释「已移除」改「提示桩」）；`core/feature_packs.py` 若引用旧名需核对（实施时确认，功能包语义不变）。
8. **`__pycache__` 残留**：`plugins/redeem_code/__pycache__/` 为 gitignore 未跟踪文件，重建源码后自然失效，无需处理。

## 测试设计

- `test/scripts/check_redeem_web.py` 扩展（沿用既有分段模式）：新码成功＋三称号到账、重复拒、小写归一、含数字格式错拒绝不写库、格式错误文案含「大写字母或数字」。
- 新增 `test/test_redeem_code_stub.py`（进程内 unittest，沿用 `test/helper.py` 的 `MockApiWrapper` + `make_group_message`/`make_private_message`）：`MockApiWrapper` 补 `delete_msg` 记录桩（可配置返回值）；断言匹配/不匹配、撤回调用参数、撤回失败仍提示、无数据库访问（插件不持有 dbmanager 写路径）。

## 规范修订要点（delta）

- `redeem-codes` 的「网页兑换入口」要求：格式校验描述改为「大写字母或数字」，补数字段场景。
- 「QQ 指令移除」要求整体废止，改名重立为「QQ 指令迁移提示桩」（RENAMED + MODIFIED）：撤回＋提示语义；归档时同步修正 spec 的 Purpose 段落中「不留提示桩」的旧表述（手动对齐，delta 机制不覆盖 Purpose）。
