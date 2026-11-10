# trpg-record-web Specification

## Purpose
网页端提供跑团记录浏览：`/trpg/records` 按开始时间倒序列出全部记录（可筛选只看自己参加的），`/trpg/records/<群号>/<目录>` 以聊天气泡形式展示过程，录制中的记录每 5 秒增量刷新。所有已登录用户可查看全部记录；图片经鉴权媒体路由提供。只支持新格式记录（含 `version: 2` 的 `meta.json` 与 `messages.jsonl`），旧格式目录不展示。

## ADDED Requirements

### Requirement: 记录列表页与筛选
`/trpg/records` SHALL 列出全部新格式记录，按开始时间倒序，每条展示群名（缺失时显示群号）、开始时间、时长、消息条数、参与人与状态徽标。页面 SHALL 提供「只看我参加的」开关，默认关闭（显示全部）；开启后只显示当前登录用户出现在该记录 `participants` 中的条目。不含 `meta.json`、`version` 不为 2 或缺 `messages.jsonl` 的目录 MUST 被跳过且不导致接口报错。

#### Scenario: 默认全部可见
- **WHEN** 登录用户打开 `/trpg/records` 且未开启筛选
- **THEN** 列表包含所有记录，包括该用户未参加的

#### Scenario: 只看我参加的
- **WHEN** 用户开启「只看我参加的」
- **THEN** 列表只剩该用户出现在参与人中的记录

#### Scenario: 旧目录不展示
- **WHEN** 记录根目录下存在只有 `meta.json` 与 `record.md` 的旧格式目录
- **THEN** 该目录不出现在列表中，接口正常返回其余记录

### Requirement: 记录状态判定
每条记录 SHALL 由文件推断状态并展示：`meta.json.end` 为 null 且存在 `messages.jsonl` 时为「录制中」；`end` 有值且无 `record.md` 时为「已结束·未导出」；存在 `record.md` 时为「已导出」。进程中途退出留下的残留录制 SHALL 按「录制中」展示，并在最新消息距今超过 10 分钟时于徽标后追加「（可能已中断）」；系统 MUST NOT 自动改写其状态或删除数据。

#### Scenario: 残留录制
- **WHEN** 存在 `end` 为 null 且最新消息时间为 30 分钟前的记录
- **THEN** 列表与详情页显示「录制中」，并附「（可能已中断）」

### Requirement: 聊天气泡展示
记录详情页 SHALL 以气泡展示消息：当前登录用户自己的消息靠右、他人消息靠左并带头像；名字行 SHALL 显示「角色卡名（昵称）」，无角色卡时只显示昵称；`role` 为 `dm` 或 `ob` 时 SHALL 显示 DM / 观察者徽标；每条 SHALL 显示时间（`HH:MM:SS`）；`sender_type` 为 `bot` 的消息 SHALL 以居中窄条样式区别于用户消息；图片分段 SHALL 渲染为图片并可在页面内放大查看；不可用图片分段 SHALL 显示占位提示。

#### Scenario: 自己的消息
- **WHEN** 记录中存在当前登录用户发送的消息
- **THEN** 该消息气泡靠右显示

#### Scenario: 机器人消息
- **WHEN** 记录中存在骰子结果
- **THEN** 该消息以居中窄条样式显示，与用户气泡有明显区别

#### Scenario: 图片消息
- **WHEN** 记录中存在图片分段
- **THEN** 页面渲染该图片，点击后可在页面内放大

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
