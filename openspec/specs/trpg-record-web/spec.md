# trpg-record-web Specification

## Purpose
网页端提供跑团记录浏览：`/trpg/records` 按开始时间倒序列出全部记录（可筛选只看自己参加的），`/trpg/records/<群号>/<目录>` 以聊天气泡形式展示过程，录制中的记录每 5 秒增量刷新。所有已登录用户可查看全部记录；图片经鉴权媒体路由提供。只支持新格式记录（含 `version: 2` 的 `meta.json` 与 `messages.jsonl`），旧格式目录不展示。

## Requirements

### Requirement: 记录列表页与筛选
`/trpg/records` SHALL 以**行式条目**列出全部新格式记录（每场团一条），按开始时间倒序。每条 SHALL 展示：团名（`meta.group_name`，缺失时显示 `团 <群号>`）、状态徽标（录制中 / 已结束）、起止时间（未结束时显示「开始 — 进行中」）、玩家人数（只统计 `participants` 中角色为空的条目，MUST NOT 计入 DM、观察者与机器人）、当前登录用户在该团中的身份、记录所用规则名（`meta.rules` 经规则注册表映射，缺失时显示「未知规则」）以及消息条数。身份展示规则：`role` 为 `dm` 显示「我的身份：DM」，为 `ob` 显示「我的身份：观察者」，为空且有角色卡名显示「我的身份：<角色卡名>（玩家）」，为空且无角色卡名显示「我的身份：玩家」，不在参与者中显示「未参与」。页面 SHALL 提供「只看我参加的」开关，默认关闭（显示全部）；开启后只显示当前登录用户出现在该记录 `participants` 中的条目。不含 `meta.json`、`version` 不为 2 或缺 `messages.jsonl` 的目录 MUST 被跳过且不导致接口报错。

#### Scenario: 默认全部可见
- **WHEN** 登录用户打开 `/trpg/records` 且未开启筛选
- **THEN** 列表包含所有记录，包括该用户未参加的

#### Scenario: 只看我参加的
- **WHEN** 用户开启「只看我参加的」
- **THEN** 列表只剩该用户出现在参与人中的记录

#### Scenario: 旧目录不展示
- **WHEN** 记录根目录下存在只有 `meta.json` 与 `record.md` 的旧格式目录
- **THEN** 该目录不出现在列表中，接口正常返回其余记录

#### Scenario: 条目字段齐全
- **WHEN** 列表中存在一场已结束、规则为 COC 7th、含 DM 与两名玩家的记录，查看者为其中一名玩家
- **THEN** 该条目显示团名、已结束徽标、起止时间、`2 人`、`我的身份：<角色卡名>（玩家）`、`COC 7th` 与消息条数

#### Scenario: 未参与与旧记录
- **WHEN** 记录没有 `rules` 字段，或查看者不在参与者中
- **THEN** 规则位置显示「未知规则」，身份位置显示「未参与」

### Requirement: 记录状态判定
每条记录 SHALL 由文件推断状态并只展示两态：`meta.json.end` 为 null 且存在 `messages.jsonl` 时为「录制中」；`end` 有值时为「已结束」。本能力 MUST NOT 引入「已结束·未导出」「已导出」等按 `record.md` 区分状态的展示，MUST NOT 依据"最新消息时间"追加「（可能已中断）」之类提示。记录状态的恢复与自动终止由 `trpg-recording-recovery` 负责，网页只读取磁盘结果，MUST NOT 自行改写或删除数据。

#### Scenario: 残留录制
- **WHEN** 存在 `end` 为 null 且最新消息时间为 30 分钟前的记录
- **THEN** 列表与详情页显示「录制中」，不附加「（可能已中断）」之类的提示

#### Scenario: 已结束记录
- **WHEN** 记录的 `meta.json.end` 有值（无论是否存在 `record.md`）
- **THEN** 列表与详情页都显示「已结束」

#### Scenario: 录制中的记录
- **WHEN** 记录的 `meta.json.end` 为 null
- **THEN** 列表与详情页显示「录制中」，不附加任何"可能已中断"提示（即使最新消息是很久以前）

### Requirement: 聊天气泡展示
记录详情页 SHALL 以气泡展示消息：当前登录用户自己的消息靠右、他人消息靠左并带头像；名字行 SHALL 显示「角色卡名（昵称）」，无角色卡时只显示昵称；`role` 为 `dm` 或 `ob` 时 SHALL 显示 DM / 观察者徽标；每条 SHALL 显示时间（`HH:MM:SS`）；`sender_type` 为 `bot` 的消息 SHALL 以居中窄条样式区别于用户消息；图片分段 SHALL 渲染为图片并可在页面内放大查看；不可用图片分段 SHALL 显示占位提示。详情页头部 SHALL 一并显示记录所用规则名（缺失时「未知规则」）。

#### Scenario: 自己的消息
- **WHEN** 记录中存在当前登录用户发送的消息
- **THEN** 该消息气泡靠右显示

#### Scenario: 机器人消息
- **WHEN** 记录中存在骰子结果
- **THEN** 该消息以居中窄条样式显示，与用户气泡有明显区别

#### Scenario: 图片消息
- **WHEN** 记录中存在图片分段
- **THEN** 页面渲染该图片，点击后可在页面内放大

#### Scenario: 头部显示规则
- **WHEN** 记录的 `meta.rules` 为 `coc7th`
- **THEN** 详情页头部显示「COC 7th」

### Requirement: 暗骰默认隐藏与开关
详情页 SHALL 默认不展示标记 `secret: true` 的消息，并 SHALL 在页面工具条提供「显示暗骰」开关。开启后这些消息 SHALL 以区别于普通机器人消息的样式插入其时间位置，关闭后 SHALL 重新隐藏。详情 API SHALL 默认过滤 `secret` 消息，仅在请求 `reveal=1` 时返回，且被过滤的消息仍计入总条数以保证增量索引稳定。

#### Scenario: 默认不显示
- **WHEN** 登录用户打开含暗骰记录的详情页且未开启开关
- **THEN** 页面不出现暗骰结果，接口响应中也不包含该消息

#### Scenario: 开启开关
- **WHEN** 用户点击「显示暗骰」
- **THEN** 页面以不带列展示暗骰消息的样式显示其完整内容位置，与普通骰子结果可区分

#### Scenario: 增量不错位
- **WHEN** 关闭开关状态下已渲染到第 10 条，第 11 条为新产生的暗骰消息
- **THEN** 下一次增量请求不会重复渲染已有消息，暗骰消息在开启开关后出现在正确位置

### Requirement: 录制中增量刷新
详情页在记录状态为「录制中」时 SHALL 每 5 秒请求一次增量消息（从已渲染条数起），并把新消息追加到末尾；状态非「录制中」或页面不可见时 MUST NOT 继续请求。用户上滑查看历史时 MUST NOT 被强制拉回底部。

#### Scenario: 增量追加
- **WHEN** 录制中的记录详情页已渲染 10 条消息，此时又产生 2 条
- **THEN** 5 秒内页面追加这 2 条，不重复渲染已有的 10 条

### Requirement: 鉴权媒体路由
记录图片 SHALL 经鉴权路由 `/trpg/media/<群号>/<目录>/<文件名>` 提供。未登录访问 SHALL 返回 401 而非 302 重定向。文件名 SHALL 严格匹配图片命名规则，含目录穿越、绝对路径或非图片名的请求 MUST 被拒绝。

#### Scenario: 未登录访问图片
- **WHEN** 未携带登录凭证请求记录图片
- **THEN** 返回 401，不返回登录页 HTML

#### Scenario: 目录穿越
- **WHEN** 请求 `/trpg/media/<群号>/<目录>/../../../data.db`
- **THEN** 请求被拒绝（400 或 404），不返回任何记录目录之外的文件

### Requirement: 导航入口
`/trpg` 与 `/trpg/records` 两个页面 SHALL 共用同一条页签（车卡 / 跑团记录），当前页面页签 SHALL 高亮。站点顶部导航条与主页导航网格 SHALL 各提供「跑团记录」入口；顶部导航条的当前分区高亮 SHALL 按最长路径前缀匹配，使 `/trpg/records` 不同时点亮「跑团」。

#### Scenario: 页签高亮
- **WHEN** 用户位于 `/trpg/records`
- **THEN** 页签「跑团记录」高亮，「车卡」不高亮；顶部导航只有「跑团记录」高亮

### Requirement: 导出回执附带网页链接
`/跑团记录 导出` 成功后的群消息 SHALL 包含该记录的网页地址 `<web_base_url>/trpg/records/<群号>/<开始时间目录>`，地址取自 `core/config.py::WEB_BASE_URL`。

#### Scenario: 导出成功
- **WHEN** 导出成功后机器人回执
- **THEN** 回执文本包含该记录的完整网页链接

### Requirement: 气泡头像与名称
记录详情的气泡 SHALL 使用与论坛、时间线一致的 QQ 头像（通过 OneBot 解析），头像不可用时回落为名字首字色块。参与者名 SHOULD 显示为「角色卡名称（QQ名称）」；括号内的 QQ 名称 MUST 使用实时解析结果，解析失败时回落消息自带昵称。接口 SHALL 在 `participants` 中提供 `display_name` 与 `avatar_url`，且 MUST NOT 因解析失败而报错。

#### Scenario: 有头像
- **WHEN** 参与者能从 OneBot 取到头像地址
- **THEN** 气泡左侧渲染 `IMG.trpg-avatar`，`src` 为该地址

#### Scenario: 取不到头像
- **WHEN** 头像解析失败或为空
- **THEN** 渲染首字色块，页面无报错

#### Scenario: 名字格式
- **WHEN** 发送者有角色卡且其当前 QQ 名称为「老张」
- **THEN** 显示「艾拉（老张）」；没有角色卡时只显示「老张」

### Requirement: 场外发言识别与隐藏开关
记录详情页 SHALL 识别场外发言：整条消息只含文本段、去掉首尾空白后被半角或全角括号完全包裹、且括号内非空。页面 MUST 提供「隐藏场外发言」开关，勾选后在客户端隐藏这些消息；开关状态 SHALL 记在 `localStorage`，刷新后保持。默认 MUST 为不隐藏。切换 MUST NOT 重新请求接口。

#### Scenario: 识别场外
- **WHEN** 某条消息文本为 `（我去倒杯水）` 或 `(等下)`
- **THEN** 该消息带 `is-ooc` 标记

#### Scenario: 不是场外
- **WHEN** 文本为 `（笑）他推门进来`、`（）`，或消息里含图片
- **THEN** 不标记为场外

#### Scenario: 开关
- **WHEN** 勾选「隐藏场外发言」
- **THEN** 场外消息立刻隐藏，刷新页面后仍隐藏；取消勾选后重新显示
