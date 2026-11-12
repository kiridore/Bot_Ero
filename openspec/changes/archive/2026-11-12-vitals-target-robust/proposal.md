# `.hp` 等数值指令的 @ 目标与空值健壮性

## Why

所有者反馈 `.hp 满 @目标` 报「指令处理出错，请检查格式」，DM 使用则提示「你还没有角色卡」。

复现出两处真问题：

1. **@ 只在独立消息段里才被识别**：有些客户端把 @ 直接拼进文本（`.hp 满 @123456789`，甚至 `.hp 满@123456789`），`_at_target()` 只扫 `type == "at"` 的段，于是目标退化成发送者自己——DM 若没有当前角色卡就会看到「你还没有角色卡」。
2. **当前值为 null 时整数运算崩溃**：1.82.1 把 `current_hp/mp/san` 改成可空后，`data.get("current_hp", maximum)` 在键存在且值为 `None` 时返回 `None`，`clamp(None, …)` 抛 `TypeError`，被兜底成「指令处理出错」。`.san` 的缺省值还错用了 SAN 上限（99−克苏鲁神话）而不是初始意志。

另外「有角色卡但没设置当前卡」与「完全没有卡」用了同一句提示，前者会误导玩家去建卡。

## What Changes

- `_at_target()` 增加文本兜底：没有 at 段时用正则从文本里取 `@<5–12 位数字>`；`_handle_amount`/`_handle_san_check` 先把这个片段从参数里剔除，`.hp 满@123` 也能解析。
- 新增 `_current()`：当前值为 `None` 时回落默认值（HP/MP 用上限，SAN 用初始意志并受上限约束）。
- 「有卡但没设当前卡」单独提示：`…还没设置当前角色卡：发送 /跑团 角色 列表 查看，再用 /跑团 角色 切换 <编号> 指定`。

## Capabilities

### Modified Capabilities

- `trpg-vitals`：目标识别与空值处理。

## Scope and Compatibility

- 只影响 `.hp/.san/.mp/.sc` 的目标解析与缺省值，正常消息段 @ 的行为不变。
- 文本兜底只认 5–12 位纯数字，避免把正文里的 `@昵称` 误当目标。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 消息段 @ | `python -m pytest test/test_trpg_vitals.py -q -k TargetFormats` | `.hp 满` + at 段 → 作用在目标身上 |
| AC02 文本 @ | 同上 | `.hp 满 @<QQ>` 与 `.hp 满@<QQ>` 都作用在目标身上 |
| AC03 空值 | 同上 | `current_hp/mp/san` 为 null 时 `.hp -2`/`.mp -3`/`.san -1` 正常结算（10→8、13→10、65→64） |
| AC04 提示 | 同上 | 有卡但未设当前卡 → 提示切换指令 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate trpg-vitals --strict` | 全量回归绿；`CHANGELOG [1.82.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
