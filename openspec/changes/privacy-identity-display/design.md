# 设计：隐私·昵称与头像公开开关

## 关键决策与依据

1. **键名 `privacy.identity_public`，单一开关**：沿用 `privacy.char_public` 的命名风格（`*_public`，缺省公开）；所有者裁定昵称与头像一个开关（Q2:A）——头像单独公开辨识意义小，匿名名配真实头像观感矛盾。
2. **匿名名 = `md5(str(qq)).hexdigest()[:8]`**：所有者指定。确定性保证跨模块一致、他人可长期认出"同一个人"，这正是匿名名优于纯隐藏的意义。
3. **头像 = identicon（Q3:B）而非灰色占位**：由 QQ 号确定性生成。实现为 5×5 左右镜像网格（3 列决定 5 列），前景色取自 md5 摘要字节，固定浅灰底，128×128 PNG。共享实现放 `core/gen_image/identicon.py`：
   - 网站侧：新增端点 `GET /identicon/{user_id}.png`（挂在 `webapp/app.py`，全站登录门控内，浏览器 `<img>` 带 cookie 可加载；输出可被浏览器缓存——内容确定性不变）。
   - bot 侧：PIL 直接调用同一函数取 `Image` 对象用于卡片绘制。
4. **判定与改写的单一落点**：`core/user_settings.py` 新增 `identity_public(user_id)`、`anonymous_name(user_id)`、`display_identity(owner_id, viewer_id, name, avatar)`。`display_identity` 是唯一改写函数：`owner == viewer` 或公开 → 原样；否则返回匿名名 + `/identicon/{qq}.png`。网站展示面调用它，禁止各模块自算 MD5；bot 可传播图片不能将 owner 作为 viewer 绕过开关。
5. **展示面接线方式**（按响应序列化处理，不改变全局昵称缓存）：
   - 时间线：`webapp/timeline/app.py::_serialize_rows` 的 users dict 是唯一咽喉——作者字段与 `{id:QQ}` 占位符都从它取值，在此处按 viewer 逐 uid 转换身份即可一次覆盖两者。
   - 论坛 `webapp/forum/app.py`（作者字段构建 + 批量解析处）、相册 `webapp/gallery/app.py`（上传者列表、打卡图列表 name_cache）、活动 `webapp/activities/app.py`（列表及详情报名成员序列化）、闹钟 `webapp/alarms/alarm_service.py`（creator_name）、直播 `webapp/live/app.py`（观众名）、工具 `webapp/tools/app.py`（created_by_*）、TRPG `webapp/trpg/app.py`（所有调用方传 viewer，角色卡所有者 display_name；保留 char_public 权限）、周报 `webapp/weekly/app.py`（响应深拷贝后处理 `{user_id,name}`，仙人彩头条按结构化中奖来源重建）。论坛同时覆盖 reply_to_name；相册过滤 user_id 与 viewer_id 分开；直播从 presence 读取时处理，避免设置变更后仍泄旧名。
   - 自看面（`webapp/profile` 的 `/api/me/*`、`webapp/app.py` 的本人信息端点）不改——viewer 恒为 owner。
   - bot 卡：`plugins/leaderboard`、`plugins/week_list` 构建行时逐用户判定；关闭者不调 `fetch_avatar_cached`（不拉真实头像），用 identicon。卡片是发到群里的公开产物、无"查看者"概念，一律按他人视角处理（本人若关闭，自己看到的榜上自己的行也是匿名——已知边界，如实记录）。
   - 活动报名表存有加入时的历史昵称：匿名在读取层做，不改存量行。
   - 个人档案图 `/档案` 与注册图均为可传播产物，无网站本人豁免，两个入口都按身份开关选择相同的展示名和头像。图片实施已完成，四入口定向测试证据见 acceptance.md。
6. **设置页**：`webapp/static/settings.js` 隐私设置分组追加开关"公开我的昵称与头像"（默认勾选），提示文案区分网站本人豁免与可传播图片；`webapp/profile/app.py::SettingsIn` 对新增 `privacy.identity_public` 严格校验 bool，存储层同样校验（共享基础已实现）。设置沿用无扩展名 `<user_id>` JSON 文件，局部深合并更新，不迁移文件名。
7. **bot 进程读个人设置**：`core/user_settings.py` 是进程无关模块（路径经 `core/config.py` 的 `paths.user_settings`，两进程同在项目根运行时指向同一目录），bot 插件直接 import 即可，不引入新通道。

## 不做的事

- 不给 identicon 加任何配置（尺寸/颜色/网格均为固定常量）。
- 不做头像文件磁盘缓存（确定性生成开销可忽略，端点输出交给 HTTP 缓存语义）。
- 不改 `/media/`、`/thumb/` 图片路由（打卡照片内容不属于身份展示面）。

## 执行 Ruling：网站身份与历史周报兼容

- 网站逐请求按查看者转换姓名和头像，本人豁免仅适用于网站；原始 ID 保留用于关联和权限。本功能不是安全匿名化，不隐藏账号号码，也不改任意用户正文、全局解析缓存或数据库历史姓名。
- 补齐周报：响应副本递归处理结构化 `{user_id,name}`。`immortal_jackpot` 的 body/stats 只能依据 `lottery.immortal` 的 digits/pool 和 winners 的 user_id/name/digits/tier 重建；来源完整且相关用户需匿名时才重建，以保持公开默认原样。覆盖大奖、仅三等奖和无人中奖三种格式，不做真实昵称全文替换。
- 经主管确认，旧头条缺少可靠来源时，不返回整页错误：仅将 headline 换成 kind=`immortal_jackpot`、title=`仙人彩历史头条`、body=`历史头条缺少身份资料，暂不展示详情。`、stats=[]。其余周报正常展示，存储不变。这是旧格式缺身份关联的兼容限制；完整来源证明 winners 为空则不降级。
- 旧中奖者缺失或非法 user_id 时，响应中的 name 固定为 `身份资料缺失`，保留非身份字段；有效 user_id 仍按查看者处理，缺 digits/tier 等字段仅导致头条降级。不能泄漏无从关联的旧姓名或因其阻断整期周报。
- 两个档案图入口均已实现并经定向测试验证图片身份开关；图案头像只做选定样本区分验证，不承诺无碰撞。设置沿用无扩展名文件，新布尔严格校验已在共享基础实现。
- 网站阶段只运行集成脚本与 API suites，不代表全量回归；后续图片及最终集成验证分开记录于 acceptance.md，不能用模拟发送替代真实QQ检查。

## 执行 Ruling：1.57.0 同批个人偏好发布与验收边界

- 三个独立提案 `privacy-identity-display`、`timeline-feed-preference`、`generated-image-watermark` 保留各自能力与验收标准，但作为同一批个人偏好变更统一发布 **1.57.0**（基线1.56.0）；原先按实施顺序写出的中间版本安排作废，不代表曾发布或需要分别发布。
- 代码、版本及文档在同批交付中同步；本次仅更新版本与文档、执行验证，不 commit/push/archive。不得因自动测试通过而删除真实客户端验收标准。
- 网站本人豁免与可传播 bot 图片不豁免分别适用；匿名身份只隐藏昵称头像，不隐藏账号关联、不替换用户正文或回写历史数据。两种多人图只逐行匿名、无水印；两个个人档案入口共用展示身份与水印规则，上传原图不变。
- 实际 Chrome + 临时配置/数据库 + 本地 webapp API 的联动与截图检查可以验证网站行为；OneBot身份资料/发送模拟不等于真实QQ客户端。真实QQ群聊、私聊档案及注册图视觉验收仍保留待验收，不归档。逐条证据与剩余事项见 [acceptance.md](acceptance.md)。
