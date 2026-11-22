# 设计

## 1. 判定来源：与时间线共用同一个函数

图库不复制任何判定逻辑，直接调 `core/user_settings.py::checkin_display(user_id) -> {"private": state, "group": state}`（时间线读的是同一个函数）。类型分流同样复用时间线的口径：

| 时间线 | 图库 |
|---|---|
| 事件 `data.private == true` → `checkin_display(author)["private"]` | `checkin_records.is_private == 1` → `checkin_display(author)["private"]` |
| 无 `data.private` → `["group"]` | `is_private == 0` → `["group"]` |

两处同源：`plugins/checkin/__init__.py` 用 `is_private = self.bot_event.group_id is None` 同时写库（`checkin.insert(..., is_private=)`）与写事件 `data.private`；网页打卡（`webapp/profile/checkin_service.py`）固定写 `is_private=True` + `data.private=True`。

## 2. 三态映射（非作者）

| 作者设置 | 时间线（非作者） | 图库（非作者） |
|---|---|---|
| `show` | 原图 URL | `thumbnail_url=/thumb/…`、`image_url=/media/…`（与现状一致） |
| `blur` | 图片 URL `+?blur=1`，点击不穿透原图 | 两支 URL **都**是 `/thumb/…?blur=1`；`image_url` 不再指向 `/media/`（点开大图即模糊图） |
| `text` | `data.images=[]` + `images_hidden: true` | 条目不下发（图库条目只有图片，没有可保留的文字信息 → 等价「图片不可见」） |
| `hidden` | 事件不下发 | 条目不下发 |

作者本人：四态都不影响，条目与 URL 与现状逐字节一致。

`image_url` 在 `blur` 态改用模糊缩略图而不是「后端模糊原图」：`thumbnails.ensure_blurred` 只对缩略图（已按 `THUMB_MAX_WIDTH/HEIGHT` 缩小）做高斯模糊，对 QQ 原图（可能数 MB、数千像素）做同等工作量的模糊会显著拖慢首屏；时间线灯箱在 `blur` 态同样停留在这张模糊缩略图上（`webapp/static/timeline.js` 的 `?blur=1` 分支），两个界面观感一致。

## 3. 分页正确性：过滤必须在切片之前

`fetch_checkins_paginated` 是「先取全部行、再 `matched[start:end]` 切片」的实现，`total`/`has_more` 都基于切片前的集合。若把过滤放在 `webapp/gallery/app.py` 的响应组装里，会出现：某页被过滤到只剩零星几条、`total` 把不可见项也计入、`has_more` 在最后一页仍为 true、「共 N 张」与实际不符。

因此新增 `keep: Callable[[CheckinImage], bool] | None` 参数，在两处构造 `CheckinImage` 的同一次循环里判定：

- `only_with_file=True`（默认）：`匹配到文件 → keep(item) → 追加`，`total = len(matched)`。
- `only_with_file=False`：`keep(item)` 过滤后 `total = len(kept)`，再切片。

不传 `keep` 时行为与改动前完全一致（个人中心 `/api/me/checkins` 就是这条路径，零变化）。

## 4. 设置读取次数

`api_checkins` 内用请求级 `dict[author_id, {"private":…, "group":…}]` 缓存：一次请求里每个作者只读一次 JSON 文件，与时间线的 `actor_states` 口径相同。仓库层仍是「取全部行」的既有实现，未新增 SQL、未改索引、未引入 N+1 查询。

## 5. 接口与权限

`/api/checkins` 增加 `Depends(get_current_user_id)` 取查看者。该端点在 `webapp/app.py` 的全站登录门控之内（不在 `_PUBLIC_PATHS`/`_PUBLIC_PREFIXES`，且属 `/api/` 前缀 → 未登录 401），因此新增依赖不改变任何鉴权结果，只是把「已登录的查看者是谁」取到处理函数里。响应模型、参数、状态码均不变。

## 6. 并发与失败路径

- 用户设置文件缺失/损坏/取值非法：`checkin_display()` 已回退 `show`，图库与时间线走同一回落，不会出现两个界面口径不一致；不会因设置读取失败而报错或吞掉条目。
- 设置文件被并发写（bot 与 webapp 两个进程都可能写）：读取用 `_read` + 原子写产物，半写文件解析失败按 `{}` 处理 → `show`；与时间线同样的风险面，本次不改变。
- 作者改设置后：下一次请求立即生效（没有缓存跨请求），与被隐藏/解禁的时间线行为一致。
- `is_private` 列缺失（极老库）：由 `core/db/_base.py` 既有迁移补列后为 `DEFAULT 0`，取群聊；`sqlite3.Row` 取不到列的情况不存在（`init_schema` 在启动时执行）。

## 7. 为什么不改 `/thumb`、`/media`（Q1:A 裁决）

服务端强制需要给媒体路由加「查看者 + 反查该文件对应打卡的 `is_private`」两次额外工作，并把 `/thumb` 的可见性耦合进全站共用路由——周报封面（`cover.images[].url` 存的是他人的 `/thumb/`）、时间线前端、Flutter 客户端都在用同一路由，改动会在这些地方产生 404 破图或额外过滤逻辑。所有者裁决取最小面：图库只保证「下发给非作者的内容」与时间线一致。代价（非作者持直链仍可取原图）与时间线当前强度相同，已写入 `specs/web-gallery.md` 作为已知边界；将来要收紧时，收口点是同一对媒体路由。

## 8. 测试清单

新增 `test/scripts/check_gallery_privacy.py`（独立进程，`test/scripts/_env.py::write_config` 生成临时 `config.yaml` 与全部数据根，红线：不触真实 `server_data`/`data.db`）：

1. 造作者 A（私聊 + 群聊各 1 条）、作者 C（1 条，默认 `show`），落 PNG 到 `config.IMAGE_ROOT`，写 `user_settings`。
2. `show` 段：A 默认设置 → 非作者 B 拿到原图两支 URL（AC03）。
3. `blur` 段：A 该项设 `blur` → B 拿到两支模糊 URL；A 自己拿到原图（AC01）。
4. `text`/`hidden` 段：B 的 `items` 不含该条目、`total`/`has_more` 扣除；A 自己仍看到（AC02）。
5. 类型分流段：私聊 `blur` + 群聊 `show`，再反向，逐项断言（AC04）。
6. `total`/分页段：3 条不同态记录 → 非作者 `total==2`，`page_size=1` 两页合计 2、末页 `has_more=false`（AC05）。
7. 媒体路由不变：`/thumb/<B>/<f>?blur=1`、`/media/<B>/<f>` 均 200（AC06 的一半；另一半由既有 `check_profile_checkins.py`、`check_special_filename_media.py` 覆盖）。
