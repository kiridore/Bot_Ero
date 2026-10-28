# 隐私·昵称与头像公开开关

## Why

网站各模块（时间线、论坛、相册、活动、闹钟、直播间、工具、TRPG、周报）与机器人生成的图片卡（积分排行榜、本周打卡板）目前无条件向他人展示每个用户的 QQ 昵称与头像。部分用户不希望 QQ 身份被公开关联，需要一个总开关隐藏昵称与头像：隐藏后昵称显示为 QQ 号 MD5 后截断 8 位的字符串，头像显示为由其派生的几何图案头像（所有者已裁定：单一开关同时控制昵称与头像；几何图案头像而非灰色占位）。

既有"隐私设置"分组已包含角色卡公开开关与打卡显示状态（show/blur/text/hidden），本提案不改变它们，仅新增开关。

## What Changes

- 新增个人设置 `privacy.identity_public`（布尔，缺省 True=公开；False=匿名身份）。存储沿用 `core/user_settings.py` 每用户无扩展名 JSON 文件 `<user_id>`；新增布尔键必须严格校验，不接受字符串、数字或 null。
- 关闭后，**他人视角**下的身份变为：
  - 昵称 → `md5(str(QQ号)).hexdigest()[:8]`（8 位十六进制小写，确定性，跨模块一致）；
  - 头像 → 由同一身份确定性生成的几何图案头像（identicon）。
- 生效面（网站按查看者判断；可传播的 bot 图片没有本人豁免）：
  - 网站：时间线（事件作者 + 标题/描述 `{id:QQ}` 占位符）、论坛作者与回复对象字段、相册上传者列表与打卡图列表昵称、活动列表及详情的报名昵称、闹钟创建者、直播观众昵称、工具创建者、TRPG 角色卡所有者、周报历史身份及仙人彩头条；
  - bot 生成图：积分排行榜卡、本周打卡板卡**按行生效**（该行用户关闭则该行显示匿名名 + 图案头像）；个人档案卡的 `/档案` 与注册图两个入口均为可传播图片，一律遵守身份开关，不因本人触发而显示真实身份。
- 网站本人查看自己保留真实昵称头像；bot 群聊**文字**消息不在范围（QQ 客户端本身显示群名片，技术上无法对他人的客户端隐藏）。
- 设置页"隐私设置"分组新增开关"公开我的昵称与头像"。

## Capabilities

### New Capabilities
- `privacy-identity-display`：匿名身份规则（MD5 昵称 + identicon 头像）、网站与生成图全部生效面、本人豁免、缺省公开。

### Modified Capabilities
无。`timeline-reporting`（上报开关）、既有打卡显示状态不在本提案内改动。

## 范围与排除

- 不拆分昵称/头像两个独立开关（所有者裁定单一开关）。
- 不匿名 bot 群聊文字消息、@ 提及、群名片——平台自身显示，超出机器人可控范围。
- 不改写活动报名表等处已存储的历史昵称：匿名在读取/序列化层实施，存量数据不动。
- 不提供"对部分人公开"细粒度控制；不引入新配置项（开关本身是个人设置，非 config.yaml 键）。
- 不改变 `privacy.char_public`、`privacy.checkin_display_private/group` 既有行为与语义。

## 验收标准

以下为保留的验收标准；最终执行证据与未完成项见 acceptance.md。目标版本 1.57.0。

| 标准 | 独立执行 | 通过条件 |
|---|---|---|
| AC01 | `python -m pytest test/test_user_settings.py` | `identity_public` 缺省 True；关闭后 `anonymous_name` = `md5(str(qq)).hexdigest()[:8]` 且同一 QQ 重复调用结果一致 |
| AC02 | `python -m pytest test/test_identicon.py` | identicon 生成确定性：同一 QQ 两次生成字节一致；所选不同 QQ 样本图案不同（不保证全域无碰撞）；输出为合法 PNG |
| AC03 | `python test/scripts/check_identity_privacy.py` | 关闭身份公开的用户：时间线（事件作者与 `{id:QQ}` 占位符）、论坛作者及回复对象、相册上传者/打卡列表、活动报名、闹钟创建者、直播观众、工具创建者、TRPG 角色卡所有者、周报结构化历史身份及仙人彩头条——对他人全部显示匿名名（头像处为站内图案头像标识）；对本人显示真实昵称；未设置用户（缺省公开）行为与现状一致 |
| AC04 | `python -m pytest test/test_generated_image_privacy.py -k rank` | 排行榜/打卡板卡构建：关闭用户的行显示匿名名与图案头像（不再拉取真实头像），公开用户行不变 |
| AC05 | `python test/scripts/check_profile_checkins.py` | 既有回归通过（时间线/打卡序列化未被破坏） |
| AC06 | `python -m pytest` | 全量回归绿（新脚本 `check_identity_privacy.py` 已被自动发现纳入） |
| AC08 | `python test/scripts/check_identity_privacy.py` | 历史活动昵称不回填；直播不补心跳即应用设置；周报大奖/三等奖/无中奖、缺来源局部降级和原 JSON 不变；不替换任意用户正文，保留关联 ID |
| AC09 | `python test/scripts/check_settings_preferences.py` | 新增布尔值严格校验，非法类型 422；局部更新不覆盖其他设置 |
| AC10 | `python -m pytest test/test_generated_image_privacy.py test/test_register_flow.py test/test_gen_image.py` | `/档案` 与注册图都遵守身份开关；匿名时昵称头像一致且不取真实头像；不以本人触发豁免 |
| AC07 | 手测：登录设置页 → 隐私设置分组出现"公开我的昵称与头像"开关 → 关闭 → 时间线中自己的事件对另一账号显示匿名名与图案头像；开关状态刷新后保持 | 通过手测确认 |

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
