# 实现发现

实现期与提案原文的偏差与经验，均已获所有者裁决或属如实记录：

1. **分页双形态（所有者裁决 A，2026-11-18）**：提案原文要求所有列表统一 `page/page_size` 偏移分页；实现时发现 forum 帖子/评论与 timeline 三条端点是**游标分页**（`cursor`+`next_cursor`，新内容插队首时页码会漂移），强行 offset 化是产品语义倒退。裁决为双形态契约：偏移列表 `page/page_size`→`{items,total,page,page_size}`；游标流 `cursor/page_size`→`{items,next_cursor}`（timeline 为 events 形态，comments 保留 total）。提案/spec/design 已同步修订。
2. **`/api/tools` 审计结论**：无分页（全量返回 `{items}`），提案中"若有 limit 一并统一"落空，不属分页端点。
3. **pydantic 响应模型的两个坑**（本轮踩过并修复）：
   - 声明了默认值的可选字段会被输出为 `null`，而原代码大量使用「条件性加键」（无键 ≠ null，如活动成员 `eta_deadline`、论坛评论 `reply_to_*`、时间线 `self_only/images_hidden`、投票帖 `polls`）。此类条件键 MUST 从模型中去掉、靠 `ConfigDict(extra="allow")` 原样透传；只有「原响应总是含该键（值可为 null）」的字段才声明 Optional。
   - bool 会被 int 声明强转（时间线 `inserted/deleted` 是 `rowcount > 0` 的 bool，声明成 int 后 `true`→`1` 破坏 `is True` 断言）。建模前先看 DB 层返回类型的语义而非值形状。
4. **图片响应路由豁免集**：`/api/me/avatar.png`、`/api/tools/icon` 返回图片而非 JSON，AC01 的 schema 断言豁免这两条（写在契约检查脚本 `BINARY_API` 常量）。
5. **深层载荷的务实建模**：规则书数据（COC options/rules）、跑团记录、DB 聚合 dict 采用「顶层键声明 + 内层 Any/透传」——保证 schema 非空与顶层类型化，不为 volatile 载荷写全量模型。Flutter 生成客户端对内层得到 Map，属可接受折衷。
6. **旧 check 脚本参数同步**：check_timeline_privacy / check_timeline_unread / check_forum_comment_threads_api 内以 `limit=` 调接口处已同步改 `page_size=`；check_alarm_calendar_api 的 `/entries.json` no-cache 检查改 `/api/nav`。
7. **首轮全量 pytest 出现 60 个 activity 单测 sqlite 瞬时失败**（单跑/复跑均绿、第二次全量起未复现），判定为 Windows 开发机临时环境问题（疑似杀软扫描新临时库），与本次改动无关，记录备查。
8. **NavLink.copy 遮蔽**：pydantic BaseModel 自带 `copy`，导航链接的 `copy` 字段用 `Field(alias="copy")` 的 `copy_text` 承载（响应按别名序列化为 `copy`）。
