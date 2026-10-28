# 时间线观看偏好：是否显示他人的打卡

## Why

时间线是网站上看到他人打卡的唯一位置（feed / poll / new 三个接口，全部登录可见）。部分用户只想把时间线当作自己的记录流，不想被他人的打卡刷屏；bot 侧 `/本周打卡图`、`/ALL` 均只查自己的图，无他人场景。所有者需求：新增"是否显示他人打卡"的个人偏好。

## What Changes

- 新增个人设置 `timeline.show_others_checkin`（布尔，缺省 True=显示，保持现状）。
- 关闭后，网站时间线**三个接口一致**滤除"他人的打卡事件"（`source == "checkin"` 且作者不是查看者）：
  - `/api/timeline`（feed）：不返回他人打卡事件，翻页游标跨过被滤事件；
  - `/api/timeline/poll`：未读计数不含被滤的他人打卡；
  - `/api/timeline/new`：不返回被滤事件，`next_after` 跨过。
- 边界（与既有打卡隐私叠加）：
  - 自己的打卡始终保留——包括自己设置为 hidden（仅自见）的打卡；
  - 他人经作者隐私设置本就对我隐藏（hidden）的打卡，叠加本设置后依旧不可见（过滤只多不少）；
  - 他人的**非打卡**事件（论坛、相册、活动等）不受本设置影响。
- bot 群指令（/排名、/本周打卡图等）是群公共内容，不做按人过滤（所有者已确认）。
- 设置页新增"时间线偏好"分组，开关"在时间线显示他人的打卡"（默认开）。

## Capabilities

### New Capabilities
- `timeline-feed-preference`：他人打卡过滤规则、三接口一致性、与打卡隐私的叠加边界、缺省显示。

### Modified Capabilities
无。`timeline-reporting` 管 bot 侧上报开关，不在本提案内。

## 范围与排除

- 仅网站时间线三个接口；不涉及 bot 指令、不涉及打卡内容本身（图片可见性仍由作者隐私设置决定）。
- 不提供"只看打卡/屏蔽某类事件"等更细的过滤维度。
- 不改变打卡显示状态（show/blur/text/hidden）语义与优先级。

## 验收标准

以下为保留的验收标准；最终执行证据与未完成项见 acceptance.md。目标版本 1.57.0。

| 标准 | 独立执行 | 通过条件 |
|---|---|---|
| AC01 | `python -m pytest test/test_user_settings.py` | `timeline.show_others_checkin` 缺省 True（未读取到键时行为与现状一致） |
| AC02 | `python test/scripts/check_timeline_privacy.py` | 关闭后 feed：他人打卡事件消失、自己的打卡保留（含自见 hidden 打卡）、他人非打卡事件保留；缺省开启用户 feed 与现状一致 |
| AC03 | `python test/scripts/check_timeline_privacy.py` | 三接口一致：poll 未读计数不含被滤他人打卡；new 不返回被滤事件且 next_after 跨过（不漏后续事件） |
| AC04 | `python test/scripts/check_timeline_unread.py` | 既有未读/回执回归通过（开关缺省时行为零变化） |
| AC05 | `python -m pytest -q`（含 API 集合） | 全量回归绿，不能以 API 集合代替 |
| AC06 | 手测：设置页出现"时间线偏好"分组与开关，关闭后时间线仅剩自己的打卡与他人非打卡事件，刷新后状态保持 | 通过手测确认 |

## 执行 Ruling：1.57.0 同批个人偏好发布与验收边界

- 三个独立提案 `privacy-identity-display`、`timeline-feed-preference`、`generated-image-watermark` 保留各自能力与验收标准，但作为同一批个人偏好变更统一发布 **1.57.0**（基线1.56.0）；原先按实施顺序写出的中间版本安排作废，不代表曾发布或需要分别发布。
- 代码、版本及文档在同批交付中同步；本次仅更新版本与文档、执行验证，不 commit/push/archive。不得因自动测试通过而删除真实客户端验收标准。
- 网站本人豁免与可传播 bot 图片不豁免分别适用；匿名身份只隐藏昵称头像，不隐藏账号关联、不替换用户正文或回写历史数据。两种多人图只逐行匿名、无水印；两个个人档案入口共用展示身份与水印规则，上传原图不变。
- 实际 Chrome + 临时配置/数据库 + 本地 webapp API 的联动与截图检查可以验证网站行为；OneBot身份资料/发送模拟不等于真实QQ客户端。真实QQ群聊、私聊档案及注册图视觉验收仍保留待验收，不归档。逐条证据与剩余事项见 [acceptance.md](acceptance.md)。
