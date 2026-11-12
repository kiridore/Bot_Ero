# 字符串格式消息支持 — 验收记录

实施分支：`master`；版本 1.82.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 解析 | `test/test_cq_parse.py` 10 例：纯文本、单个 at、文本+at、多段、转义、参数内逗号、数组原样、空值 | 通过 |
| AC02 事件归一 | 同文件：`Event({"message": ".hp 满 [CQ:at,qq=100000002]"})` → `[text, at]`；数组形态返回同一对象 | 通过 |
| AC03 落地效果 | `TestCqStringMessage::test_at_in_cq_string`：字符串格式提令，目标角色 HP 回满到 10 | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **867 passed**（5:06）；`openspec validate onebot-message --strict` valid；`CHANGELOG [1.82.3]` 与 `BOTERO_VERSION = "1.82.3"` 一致 | 通过 |

## 实测与裁定

- **上游核对**：
  - AtSegment 结构 `{type:"at", data:{qq, name}}`（`qq` 为数字字符串或 `all`）——<https://api.luckylillia.com/schema-189483997.md>
  - 字符串格式与转义规则——<https://github.com/botuniverse/onebot-11/blob/master/message/string.md>（`&`→`&amp;`、`[`→`&#91;`、`]`→`&#93;`，CQ 参数内额外 `,`→`&#44;`）
- **归一化位置**：放在 `Event.message`，而不是各插件，避免每加一个插件就重复一遍格式判断；数组形态直接返回原对象，零拷贝零行为变化。
- **上一版兜底保留**：文本 `@QQ号` 的识别不再承担「CQ 兼容」职责，但保留以覆盖把 @ 打成纯文本的客户端，且只认 5–12 位数字。
- **未做**：不收 `raw_message` 之外的其它字段（如 `message_sent` 事件的格式差异），也不做「发送侧字符串格式」兼容——发送一律用消息段数组。
