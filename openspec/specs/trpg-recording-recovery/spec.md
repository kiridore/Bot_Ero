# trpg-recording-recovery Specification

## Purpose
让跑团录制状态以磁盘为准：机器人启动时扫描 `end` 为 null 的记录目录，7 天内还活跃的自动续录并在记录里标注中断与恢复，超时或所属群已解散的自动终止；运行期每 5 分钟检查一次录制中的群是否还在。录制数据本身（`meta.json`、`messages.jsonl`、`imgs/`）始终实时落盘，恢复只重建内存状态，不重写历史。

## Requirements

### Requirement: 启动时从磁盘重建录制状态
`main.py` 启动时 SHALL 调用 `recover_recordings()`，扫描 `<python_data_path>/trpg_records/<群号>/<开始时间目录>/` 中 `meta.json` 的 `version` 为 2 且 `end` 为 null 的记录目录，按下列顺序判定：群已不在群列表 → 终止；最后一条消息时间（无消息时取开录时间）距今超过 7 天 → 终止；否则续录。同群存在多条待恢复目录时 SHALL 只续录 `start` 最新的一条，其余终止。续录 SHALL 恢复 `start`（取自 `meta.json`，MUST NOT 改成重启时间）、`participants`、`roles`、记录目录与图片编号（从 `imgs/` 现有最大编号 +1 继续，MUST NOT 覆盖已有图片）。群列表接口不可达时 SHALL 跳过"群已解散"判定，只按 7 天规则处理。

#### Scenario: 重启后续录
- **WHEN** 存在 `end` 为 null、最后消息在 2 天前的记录，机器人重启
- **THEN** 该群进入录制状态，后续群消息写入同一记录目录，`meta.json.start` 保持原值

#### Scenario: 超时终止
- **WHEN** 存在 `end` 为 null、最后消息在 8 天前的记录
- **THEN** 该记录被写入 `end`（等于最后一条消息时间）并生成 `record.md`，不进入录制状态

#### Scenario: 图片编号接续
- **WHEN** 续录前目录内已有 `img_0003.jpg`
- **THEN** 续录后新图片从 `img_0004` 开始编号

### Requirement: 中断与恢复留痕
续录时 SHALL 向 `messages.jsonl` 追加一条机器人消息，文本包含中断时间（该记录最后一条消息的时间）与恢复时间（本次恢复的时刻）。机器人连上 OneBot 后的首个心跳周期 SHALL 在该群发送一次恢复公告，内容包含该场录制开始时间与「如需结束请由 DM 发送 `/跑团 记录 结束`」；公告发送失败 SHALL 在下一个心跳周期重试。

#### Scenario: 中断留痕
- **WHEN** 一条记录在 2026-11-14 23:10 中断，机器人在 2026-11-15 20:05 恢复
- **THEN** `messages.jsonl` 末尾出现机器人消息「录制于 2026-11-14 23:10 中断，2026-11-15 20:05 恢复」

#### Scenario: 恢复公告只发一次
- **WHEN** 续录成功且机器人已连上 OneBot
- **THEN** 该群在下一个心跳周期收到一次恢复公告，之后不再重复发送

### Requirement: 运行时群解散检测
机器人 SHALL 每 5 分钟通过心跳检查一次（按分钟去重，同一分钟只执行一次）；仅当存在录制中的群时才调用 `get_group_list`，没有录制时 MUST NOT 调用。群列表返回成功且其中不含某个录制中的群时 SHALL 自动终止该群录制；`get_group_list` 失败（返回 `None`）时 MUST NOT 终止任何录制。

#### Scenario: 群被解散
- **WHEN** 某群录制中，心跳取到的群列表不含该群
- **THEN** 该群录制被终止，`meta.end` 写入最后一条消息时间，并生成 `record.md`

#### Scenario: 接口故障不误杀
- **WHEN** `get_group_list` 超时或返回失败
- **THEN** 本轮不做任何终止

#### Scenario: 无录制不轮询
- **WHEN** 没有任何群处于录制中
- **THEN** 心跳不调用 `get_group_list`

### Requirement: 自动终止的归档
自动终止（超时或群解散）SHALL 写入 `end` 并生成 `record.md`，`end` 取值 SHALL 为该记录最后一条消息的时间（无消息时取开录时间），MUST NOT 使用检测到终止的时刻。群已解散时 MUST NOT 尝试向该群发送消息。

#### Scenario: 解散后归档时间
- **WHEN** 某群最后一条消息在 2026-11-10 22:00，两天后检测到群已解散
- **THEN** 该记录 `end` 为 2026-11-10 22:00，网页显示「已结束」
