# 打卡分享卡 DOM 化设计（取代 PIL 服务端渲染）

日期：2026-09-12 · 状态：已确认（用户裁定）
上游：`2026-09-12-profile-checkin-tab-share-card-design.md`（原 spec；本文取代其 D3/D4/D5，修订 D6/D7）

## 背景与动机

原 D3/D4 的服务端 PIL 方案（`GET /api/me/checkin/{id}/share.png`）存在严重性能问题：每次点击预览都触发一次完整服务端渲染（OneBot 昵称解析冷缓存可达 30s 级 + 头像下载 + PIL 合成），且长请求期间弹层交互异常。改为活动分享长图同款技术（vendored `html-to-image.min.js`）：**预览即 DOM 卡片（零网络、瞬时），点「下载图片」才转 PNG**。

## 决策表（增量）

| # | 决策 |
|---|------|
| E1 | 分享卡改为前端 DOM 渲染：`buildShareCardNode(record)` 构建固定 1080px 逻辑宽卡片，弹层内经 `transform: scale()` 缩放预览；数据全部来自已加载的 `profileData` + lightbox 记录，零网络 |
| E2 | 「下载图片」时才转换：`htmlToImage.toPng(card, {width:1080, height:offsetHeight, pixelRatio:1, backgroundColor:"#f5f5f5", style:{transform:"none"}})` → `<a download>`；转换期间按钮 disabled +「生成中…」，失败 alert（活动页同款交互） |
| E3 | 头像同源代理：新增 `GET /api/me/avatar.png`——`avatar_service.cached_avatar_path(user_id)` 查/写 `avatar_cache/share_{uid}.png` 磁盘缓存（未命中经 `resolve_avatar_url` 下载，支持 `file://` 测试钩子），`FileResponse` + `Cache-Control: private, max-age=86400`；不可用 404 → 前端降级 CSS 首字圆。（QQ 头像 CDN 无 CORS 头，跨域图无法内联进 PNG） |
| E4 | 视觉契约不变（继承原 D4/D5/D6）：浅色卡（#f5f5f5/#2d2d2d/#6e6e6e）；头像+昵称 → 日期（含星期）→ 照片 → 「连续打卡 N 天 · 累计 M 张」→ footer「Power by 小埃同学」；照片区纯 CSS 实现 contain + `max-height:1250px` 上限 + 模糊同图铺底——任何宽高比成品恒定 1080 宽、总高有上界 |
| E5 | `/api/me/profile` 响应新增 `total_checkin_images`（复用 `db.checkin.count_images`，口径=非补卡图片记录总数）；连击沿用 `streaks.current_daily` |
| E6 | 服务端 PIL 路径整体删除：`webapp/profile/share_service.py`、`/api/me/checkin/{id}/share.png` 路由、`core/gen_image/checkin_share_card.py` 及其单测、`webapp/gallery/repository.fetch_checkin_by_id`（唯一调用者即 share_service）；git 历史留档 |
| E7 | 弹窗关闭异常随长请求移除而消失；`openLightbox` 改收完整记录 `{id, image_url, checkin_date}`（打卡网格与当日弹窗两个调用点同步） |
| E8 | CHANGELOG 原地修订**未发布**的 `[1.46.0]` 节（未 push，不 bump 版本、不加新节）；`specs/web-gallery.md` 路由行对换（share.png → avatar.png）+ profile 字段补记 |

## 边界

- html-to-image 已 vendored（`webapp/static/vendor/html-to-image.min.js`，活动页在用），不新增依赖
- `pixelRatio: 1`（对齐活动页；iOS Safari canvas 面积上限考虑）
- 打卡列表 API（`/api/me/checkins`）与 Tab/网格前端不动；本变更只影响分享链路
