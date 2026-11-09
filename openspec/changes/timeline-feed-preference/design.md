# 设计：时间线观看偏好

## 关键决策与依据

1. **键名 `timeline.show_others_checkin`**：观看偏好（我看别人），不是隐私（别人看我），独立于 `privacy.*` 顶层分组；缺省 True 保持现状。
2. **接线点**：`webapp/timeline/app.py` 已有"Python 侧可见性过滤 + 逐页补取"机制（`_visibility_ctx` / `_visible_entry` / `_FEED_FETCH_PAGES` 补页循环，为打卡四态隐私而建）。他人打卡过滤在同一循环、同一判定处追加一个查看者级条件：`source == "checkin" and actor_key != str(viewer) and not show_others_checkin(viewer)`。每请求读一次设置（不 lru——设置可变），成本与既有的每作者 JSON 读取同量级。
3. **三接口共用同一判定函数**，保证 feed/poll/new 可见集合一致；poll/new 的未读计数与游标推进随过滤自然正确（被滤事件不进入可见集，`next_after` 沿用"含被滤行的已消费批次取尾"的既有做法）。feed 的5页补取上限可能返回空页但仍有 cursor，前端 `loadPage` 必须自动继续读取，直到有可见事件或游标取尽；不能把空页当结束。
4. **设置页**：`webapp/static/settings.js` 新增“时间线偏好”分组与开关，读写走既有 `/api/me/settings`。执行裁定：原模型只有 privacy，不会自动放行 timeline；必须显式扩展 SettingsIn/SettingsOut 和 GET/PUT 返回值，新增布尔键严格验证，序列化排除未提供字段以保留深合并局部更新。已补 API 往返、非法值及互不覆盖测试。
5. **不动 bot**：群指令是群公共产物，按人过滤在群里无意义（所有者已确认 Q6）。

## 不做的事

- 不做事件类型维度的通用过滤框架（只有打卡一种，YAGNI）。
- 不缓存查看者设置跨请求（每请求一次 JSON 读，量级可忽略）。

## 执行 Ruling：1.57.0 同批个人偏好发布与验收边界

- 三个独立提案 `privacy-identity-display`、`timeline-feed-preference`、`generated-image-watermark` 保留各自能力与验收标准，但作为同一批个人偏好变更统一发布 **1.57.0**（基线1.56.0）；原先按实施顺序写出的中间版本安排作废，不代表曾发布或需要分别发布。
- 代码、版本及文档在同批交付中同步；本次仅更新版本与文档、执行验证，不 commit/push/archive。不得因自动测试通过而删除真实客户端验收标准。
- 网站本人豁免与可传播 bot 图片不豁免分别适用；匿名身份只隐藏昵称头像，不隐藏账号关联、不替换用户正文或回写历史数据。两种多人图只逐行匿名、无水印；两个个人档案入口共用展示身份与水印规则，上传原图不变。
- 实际 Chrome + 临时配置/数据库 + 本地 webapp API 的联动与截图检查可以验证网站行为；OneBot身份资料/发送模拟不等于真实QQ客户端。真实QQ群聊、私聊档案及注册图视觉验收仍保留待验收，不归档。逐条证据与剩余事项见 [acceptance.md](acceptance.md)。
