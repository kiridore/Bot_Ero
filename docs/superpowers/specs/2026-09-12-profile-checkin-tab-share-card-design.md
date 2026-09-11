# 个人中心打卡卡片 Tab 与分享卡设计

日期：2026-09-12 · 状态：已确认（用户裁定）

## 目标

个人主页新增「打卡记录」Tab（与「称号」并列），卡片式浏览自己的全部打卡图；查看打卡时可生成美观的分享卡片图。任何宽高比（全景横图、超长截图）的打卡图，生成的分享卡尺寸都收敛在合理上界内。

## 决策表

| # | 决策 |
|---|------|
| D1 | 卡片粒度：每张打卡图一张卡；按月分组标题 + 响应式网格；时间倒序、每页 24 张、「加载更多」分页 |
| D2 | Tab 结构：现有「称号」区块（筛选 + 列表）原样搬入 Tab 面板，Tab 栏「称号 \| 打卡记录」置于热力图下方，默认称号 |
| D3 | 分享入口：lightbox 底部「生成分享卡片」按钮 → 预览弹层 `<img src="/api/me/checkin/{id}/share.png">`（cookie 认证）+ 「下载图片」（`<a download>`） |
| D4 | 分享卡服务端 PIL 生成（新模块 `core/gen_image/checkin_share_card.py`），浅色简洁风对齐 `profile_card.py` 色板；固定宽 1080，成品总高 ≤ ~1700 |
| D5 | 照片区宽高比约束：box = 1000×1250（左右各 40 padding）；原图 **contain** 缩放进 box，空隙用放大模糊的同图背景铺满（微信分享卡惯例）；极端比例不裁剪、不产生超长卡 |
| D6 | 分享卡内容：圆形头像 + 昵称 → 打卡日期（含星期）→ 照片 → 统计行「连续打卡 N 天 · 累计 N 张」→ footer「Power by 小埃同学」；头像获取失败回退昵称首字圆形占位 |
| D7 | 列表 API `GET /api/me/checkins?page=1` 返回 `{items, page, has_more}`（item = id/checkin_date/thumbnail_url/image_url）；月份分组由前端按 `checkin_date` 前缀计算（YAGNI：不加后端聚合） |
| D8 | 图片读取兼容：EXIF 旋转（`ImageOps.exif_transpose`）、GIF/WebP 取首帧、带 alpha 通道转 RGB 白底 |
| D9 | 无本地文件的记录不进列表（`only_with_file=True`）；分享接口对无文件/非本人/不存在 → 404 |
| D10 | 测试以进程内 pytest 为主（API 行为 + 生成函数尺寸断言）；不新增 DOM 回归测试（项目无 profile 既有 DOM 用例） |

## 改动点

- `webapp/profile/app.py`：新增 `GET /api/me/checkins`（复用 `webapp/gallery/repository.fetch_checkins_paginated`）、`GET /api/me/checkin/{record_id}/share.png`
- `core/gen_image/checkin_share_card.py`（新）：`build_checkin_share_card(record, display_name, avatar_bytes, stats) -> PIL.Image`；复用 `fonts.py` / `avatar_helper.py`
- `webapp/static/profile.html` / `profile.js`：Tab 栏 + 打卡网格（月分组、加载更多）、lightbox 记录 id、分享预览弹层
- `core/web/static/profile.css`：Tab、卡片网格、预览层样式
- 测试：`test/test_profile_checkins_api.py`（分页 + share.png 200 / 越权 404）、`test/test_checkin_share_card.py`（极端比例输入 → 输出尺寸上界断言）
- 文档：`CHANGELOG.md` + `core/config.py::BOTERO_VERSION` minor bump；`specs/web-gallery.md` 新路由（web 路由不在 kb/OPERATIONS.md，该文件仅记 OneBot API）

## 边界

- 分享接口只允许访问本人记录（与 `/api/me/*` 全域一致）
- 超大输入图先等比降采样再合成（避免 OOM/慢请求）；打卡图本身已有上传大小上限兜底
- 统计口径：「连续」= `db.checkin.streaks()` 的 `current_daily`；「累计 N 张」= 该用户非补卡图片记录总数
- QQ 侧插件、指令表、菜单文本零改动（纯 webapp 功能）
