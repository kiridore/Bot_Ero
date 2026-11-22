# 设计

## 1. 协议：用空字符串表达「图片不可看」

选项对比：

| 方案 | 客户端改动 | 契约动静 | 评价 |
|---|---|---|---|
| A 新增 `image_hidden: bool` | 两端都要读新字段 | 改 schema → 刷新 `app/openapi/openapi.json` + 重跑 App 生成客户端 | 显式，但为一个布尔值付全套生成成本 |
| **B 两支 URL 下发空串**（采纳） | 网页加一个空串分支；App 的 `AuthImage` 已有空串分支 | 字段集不变，快照/生成代码零刷新 | 最小且语义唯一——改动前 `thumbnail_url`/`image_url` 永不为空 |

选 B 的关键事实：`app/lib/features/gallery/auth_image.dart` 的 `build()` 首行就是 `if (widget.url.isEmpty) return placeholder;`，`checkin_card.dart` 传入的是 `thumbnailUrl.isEmpty ? imageUrl : thumbnailUrl`。因此「隐藏态两支 URL 都为空」在 App 上天然渲染成 3:4 占位灰块，卡片（昵称+时间）照常显示，无需任何 App 逻辑改动。

空串不会与既有语义冲突：`has_file` 仍是「文件在不在磁盘上」（占位态的 `has_file` 为 true，因为文件确实存在，只是当前查看者无权看）；`only_with_file` 过滤也仍按文件存在判断。两端 UI 目前都不消费 `has_file`（已 grep 确认），所以保持它的字面语义最安全。

## 2. 服务端映射（`webapp/gallery/app.py::api_checkins`）

| 查看者 | 作者设置（该记录类型） | `thumbnail_url` | `image_url` |
|---|---|---|---|
| 作者本人 | 任意（含 `text`/`hidden`） | `/thumb/<作者>/<文件名>` | `/media/<作者>/<文件名>` |
| 非作者 | `show` | `/thumb/<作者>/<文件名>` | `/media/<作者>/<文件名>` |
| 非作者 | `blur` | `/thumb/<作者>/<文件名>?blur=1` | `/thumb/<作者>/<文件名>?blur=1` |
| 非作者 | `text` / `hidden` | `""` | `""` |

类型判定仍读 `checkin_records.is_private`，状态仍取 `core/user_settings.py::checkin_display()`（每作者每次请求只读一次，请求级缓存），与时间线同源。

**分页语义回退**：`keep` 过滤删除后 `total`/`has_more` 回到「全部记录」口径，页码不再有空洞——2.4.1 引入的「切片前过滤」不再需要，`fetch_checkins_paginated` 恢复原形（`is_private` 保留在 `CheckinImage` 上）。

## 3. 前端：占位卡（`webapp/static/gallery.js` + `core/web/static/base.css`）

```js
const hasImage = Boolean(item.thumbnail_url || item.image_url);
```

- `hasImage === false`：卡片的图片位插入 `<div class="card-placeholder"><span>图片仅作者可见</span></div>`，`card` **不注册** `click`（`cursor` 由 CSS 改成默认），避免点开灯箱后只剩「原图加载失败」。
- `hasImage === true`：与现在逐字一致（`<img>`、`dataset.fullSrc`、灯箱）。

CSS：

```css
.card-placeholder {
  aspect-ratio: 3 / 4;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--tint);
  color: var(--ink-soft);
  font-size: 0.75rem;
  cursor: default;
}
```

`aspect-ratio: 3 / 4` 与 App 的 `_fallbackAspectRatio = 3 / 4` 对齐（双端一致约束：同一语义两端同形）。无图片时卡片高度固定，瀑布流不会因占位卡塌陷。

## 4. 时间线保持原样

时间线的 `hidden` 仍是「事件对非作者不下发」——这是 2.2.0 起既定的产品语义，本次不动。图库与时间线的差异由所有者本次明确要求：图库是「打卡存在性」的展示面，卡片可见、图片不可见。

`specs/conventions.md` 的双端一致约束因此改写为两条互不冲突的规则：

- **条目级不可见**（整条业务对象对该查看者不存在，如时间线的 hidden 事件）→ 服务端不下发，客户端不得用占位表达。
- **图片级不可见**（业务对象可见但图片位不可看，如图库 `text`/`hidden` 的记录）→ 服务端下发条目并把图片 URL 置空，客户端渲染占位并注明「图片仅作者可见」，不得回落到本地缓存或直链。

## 5. 边界与失败路径

- 设置文件缺失/损坏/非法值：`checkin_display()` 回退 `show` → 与时间线同口径，不会把图片位误置空。
- `is_private` 历史行为 0：按群聊取 `checkin_display_group`，与时间线「无 `data.private`」回落一致。
- 空 URL 与灯箱：前端不绑定点击，`openLightbox` 不会被调用；即使用户手工构造 `/media/…`，行为与 2.4.1 相同（既有已知边界，不变）。
- App 侧无逻辑改动：`AuthImage` 空串 → 占位；`CheckinCard` 仍在图片位下方渲染昵称+时间。文案对齐（「图片仅作者可见」）随 `app/openspec/` 提案落地，不阻塞本次服务端行为。

## 6. 测试清单

- `test/scripts/check_gallery_privacy.py`（改）：`text`/`hidden` 断言条目存在且两支 URL 为空串、`has_file` true；`total`/分页断言改为全量口径；`show`/`blur`/作者视角三段保持不变（回归保护）。
- `test/test_gallery_render.js`（新增）：空 URL → `.card-placeholder` 存在、`.card` 无 `click` 效果（点击后 `#lightbox` 仍为 `hidden`）；非空 URL → `<img>` 存在、点击后灯箱显示。
- 既有脚本 `check_profile_checkins.py`、`check_special_filename_media.py`、`check_webapp_api_contract.py` 全绿（`/api/me/*` 与媒体路由不受影响）。
- 全量 `python -m pytest -q`。
