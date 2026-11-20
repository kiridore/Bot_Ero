# 设计

## 1. 为什么必须与查看者无关

现有载荷只有**查看者相关的变换结果**，没有作者设置的权威值：

| 作者设置 | 非作者收到的 | 作者本人收到的 |
|---|---|---|
| `show` | 原图，无标记 | 原图，无标记 |
| `blur` | 图片 URL 带 `blur=1` | 原图，无标记 |
| `text` | `images: []` + `images_hidden: true` | 原图，无标记 |
| `hidden` | 事件不下发 | 事件 + `self_only: true` |

作者视角完全看不到「我已把图片设为模糊/仅文字」，非作者也只能从图片形态反推，且 `show` 与「历史事件」不可区分。所有者要求「这个标记不论本人还是其他人都能看到标记」，因此字段必须由**作者的设置**直接决定，不能按查看者变换后再输出。字段值即 `checkin_display()[private|group]` 的原值。

`hidden` 是唯一无法让非作者看到标记的态：该态事件本身对非作者不下发（既有安全边界，本次不改）。「与查看者无关」的准确含义是：**对同一条被下发的事件，所有能收到它的查看者拿到的值完全相同**；hidden 事件的唯一接收者是作者，值为 `"hidden"`。

## 2. 计算与放置

`_visibility_ctx` 已经为分页逐条判定四态；在同一个循环里顺手记下 `states[eid] = state` 即可，不增加任何设置读取：

```python
def _visibility_ctx(entries) -> dict:
    hidden, blur_ids, text_ids = set(), set(), set()
    states: dict[str, str] = {}
    actor_states: dict[str, dict[str, str]] = {}
    for eid, source, actor_key, data_raw in entries:
        if source != "checkin":
            continue
        if actor_key not in actor_states:
            actor_states[actor_key] = user_settings.checkin_display(actor_key)
        ...
        state = actor_states[actor_key]["private" if is_private else "group"]
        states[eid] = state
        ...
    return {"hidden": hidden, "blur": blur_ids, "text": text_ids, "states": states}
```

`_serialize_rows` 写入字段时只看 `vis["states"]`，**不放进** `viewer_id is not None` 的展示变换分支：

```python
checkin_state = vis["states"].get(eid) if vis is not None and source == "checkin" else None
...
**({"checkin_state": checkin_state} if checkin_state else {}),
```

因此即使 `_serialize_rows` 被以 `viewer_id=None` 调用（无查看者上下文），只要传入 `vis` 仍能输出作者原值；`viewer_id` 只影响既有的过滤/改写结果。

性能：仍是每作者每页一次 JSON 读取（`actor_states` 缓存）；`states` 只多一个 dict 写入，无额外 I/O、无 SQL、无并发变化。`feed` 的补页循环会多次调用 `_visibility_ctx`，但每次只为当前批次的作者读一次设置，与改动前相同。

## 3. 条件键语义与 OpenAPI 声明

既有实现用「无键 ≠ null」表达条件键（`self_only`、`images_hidden`），因此 `EventOut` 用 `extra="allow"` 透传。但所有者要求字段**显式声明**，否则 OpenAPI 快照里没有它，客户端生成物仍拿不到类型。

声明 `checkin_state: str | None = None` 后，FastAPI 默认会把缺失字段序列化成 `"checkin_state": null`，与「非打卡事件不含该键」冲突。采用路由级 `response_model_exclude_unset=True`：

- 处理函数为每条事件显式写入的键（`seq/id/source/.../description/target/data/unread`，值可为 `null`）视为 set，**照旧输出**；
- 只有 `checkin_state` 在非打卡事件中从未提供，视为 unset，**从响应中省略**；
- `TimelineFeedOut.next_cursor`、`TimelineNewOut.next_after` 由处理函数显式写入，即使为 `null` 也保留。

已在 pydantic 2.13.1 / FastAPI 0.115.6 下用嵌套 `BaseModel` 验证 `exclude_unset` 会递归到 `events[]`（`{"items": [{"a": 1}, {"a": 2, "b": "x"}]}`），并用真实端点断言非打卡事件无键、打卡事件有键。

不采用 `response_model_exclude_none=True`：它会把 `description: null`、`target: null`、`data: null`、`next_cursor: null` 一并删掉，属于既有契约破坏，超出本次范围。

不采用「继续靠 `extra="allow"` 透传」：字段不会出现在 OpenAPI schema，客户端生成物无法类型化，违背本次「让客户端看到标记」的目标。

## 4. 与既有三信号共存

| 信号 | 语义 | 查看者相关 | 输出条件 |
|---|---|---|---|
| `checkin_state` | 作者设置的权威原值 | 否 | 每条 `source=checkin` 事件 |
| `self_only: true` | 该事件作者自见（hidden） | 是（仅作者） | hidden 事件且查看者=作者 |
| `images_hidden: true` | 图片已被服务端剥除 | 是（仅非作者） | text 事件且非作者且有图 |
| `?blur=1` URL | 图片已被服务端改写为模糊版 | 是（仅非作者） | blur 事件且非作者且有图 |

前三者都不足以单独表达 `show` 与其他态，也无法让作者看到自己的标记；`checkin_state` 是补充的权威状态，不是替换。既有字段/URL 行为全部保留，客户端可同时渲染「隐私标记」（新字段）与「图片仅作者可见/模糊」提示（旧信号）。

## 5. 边界与失败路径

- 用户设置文件缺失/非法：`user_settings.checkin_display()` 已回退 `show`，`checkin_state` 与既有过滤使用同一来源，不会出现标记与过滤口径不一致。
- 历史事件无 `data.private`：按群聊类型取 `checkin_display_group`，与现有可见性一致。
- 无图片的 blur/text 事件：`checkin_state` 照常输出（标记的是作者设置，不是图片处理结果）；`images_hidden` 仍只在有图时出现（既有 P2 守卫不变）。
- `_serialize_rows` 未传 `vis`（理论路径）：不输出 `checkin_state`，不报错；现有两个调用点都计算并传入 `vis`。
- 数据库：零 schema 变更、零迁移、零回填；字段每次读取时计算，作者改设置后下一次翻页立即生效（与现有过滤一致）。
- bot 进程：零改动。社区版与私有版共用同一实现，无 edition 分支。

## 6. 测试清单

1. `test/scripts/check_timeline_privacy.py` 扩展：
   - show（C 的默认设置）：作者 C 与非作者 A/B 对同一事件都得到 `"show"`；
   - blur（A 的群聊经旧键迁移为 blur）：A 与 C 对 `checkin:a-group` 都得到 `"blur"`；
   - text（B 私聊）：B 与 C 对 `checkin:b-priv` 都得到 `"text"`；
   - hidden（A 私聊）：A 得到 `"hidden"`，C 的 feed/new/poll 仍没有该事件；
   - 非打卡（forum）：响应无 `checkin_state` 键；
   - 既有 `self_only`/`images_hidden`/`blur=1`/分页/poll 断言不改，全部继续通过。
2. OpenAPI schema 断言（同一脚本）：`components.schemas.EventOut.properties.checkin_state` 存在且为 string|null、不在 `required`。
3. `test/scripts/check_webapp_api_contract.py` 既有段全绿（确认 `exclude_unset` 未改变其它契约）。
4. 全量 `python -m pytest -q`。
5. 快照：`cd app && python tool/export_openapi.py ..`，diff 归因为 `EventOut.checkin_state` + 已确认的 2.1.x 三处基线补齐。
