# 跑团网页端在线车卡设计

> 日期: 2026-08-02
> 状态: 已确认（设计评审通过）

## 背景

跑团功能包（trpg）现有 QQ 端角色卡（`trpg_char`，4 步引导式创建）、骰子（`trpg_dice`，引用角色属性）、跑团记录（`trpg_session`）。QQ 引导只是 DND 角色卡填写体验的精简子集，无法支撑完整的车卡工作。本项目为跑团包新增基于现有网页端架构（`checkin_gallery` FastAPI 应用）的**在线车卡**：Excel 式单页分区表格全量填写 + 查看。

核心架构决策：**角色卡数据改为纯 JSON 文件存储，弃用 SQLite 表**——角色卡字段开放性强（特性/法术/自定义字段），JSON 可存任意嵌套结构，摆脱 schema 演进。同时沉淀**绑定 QQ 号的通用个人设置体系**，隐私开关为第一个用例。

## 需求确认

| 项 | 结论 |
|----|------|
| 网页端体验 | 单页分区表格，Excel 式单元格直接编辑，一次性完成所有车卡工作 |
| 存储 | 纯 JSON 文件（每角色一文件 + 每用户 meta.json），弃用 `dnd_characters` 表 |
| 旧数据 | 直接放弃（开发期测试数据，无真实用户） |
| QQ 端 | 保留 查看(仅自己)/列表/切换/删除；废弃 创建/编辑/@查看他人 |
| 骰子契约 | 标准键保留（`str_score` 等 + 中文技能名），`finalize()` 照算，骰子零改动 |
| 查看权限 | 登录用户可查看所有人；受每用户隐私开关 `char_public` 约束 |
| 隐私开关 | 总开关一个（`privacy.char_public`），两端统一遵守（QQ 端已不能看他人） |
| 规则计算 | 前端实时计算提示 + 保存时服务端 `finalize()` 重算校验 |
| 多角色管理 | 网页端完整支持（新建/编辑/激活/删除），QQ 端为补充 |
| 通用设置体系 | 搭骨架（模块 + 接口）+ 车卡隐私一个用例；称号等现有设置不迁移 |

## 数据层

文件系统存储（`server_data/` 下，bot 与 web 双进程共用，`tmp + os.replace` 原子写）：

```
server_data/trpg_chars/<user_id>/meta.json        # {"current_id": 3, "order": [1,2,3]}
server_data/trpg_chars/<user_id>/<char_id>.json   # 单个角色完整数据（任意嵌套 dict）
server_data/user_settings/<user_id>.json          # 通用设置 {"privacy": {"char_public": true}}
```

### 新增 `core/character_store.py`（纯 stdlib，bot 与 web 均可 import）

- `list_chars(user_id)` / `get_char(user_id, char_id)` / `create_char(user_id, data) -> int`
- `update_char(user_id, char_id, data)` / `delete_char(user_id, char_id)` / `set_current(user_id, char_id)` / `get_current(user_id)`
- id 分配：`meta.order` 递增；删除当前角色后自动切下一个（复用现有语义）
- 越权防护：所有函数以 `(user_id, char_id)` 为入参，路径由 `user_id` 派生，不存在跨用户路径
- `user_id` 做合法性校验（仅数字），`char_id` 做整数校验，防路径穿越

### 新增 `core/user_settings.py`（纯 stdlib）

- `get_settings(user_id) -> dict`（文件不存在返回 `{}`）
- `update_settings(user_id, patch: dict)`（深合并后原子写）
- 本次约定键：`privacy.char_public`（bool，默认 true）

### 规则模块迁移

`plugins/trpg_char/rules.py` + `character.py`（纯逻辑，无插件代码）→ `core/trpg/rules.py` + `core/trpg/character.py`。`core/__init__.py` 为空，import 无副作用。`plugins/trpg_char/` 改为从共享模块 re-export 兼容。

### 弃用清理

- 删除 `core/db/character.py`（CharacterManager）
- 删除 `core/db/_base.py` 中 `dnd_characters`、`dnd_current_character` 建表语句
- 旧表数据直接放弃
- `checkin_gallery/config.py` 增加 `TRPG_CHARS_ROOT` / `USER_SETTINGS_ROOT` 路径常量

## 后端 API（`checkin_gallery/app.py` 新增端点）

沿用现有鉴权（`Authorization: Bearer <登录密钥>`，`get_current_user_id`）。

车卡端点：

| 端点 | 说明 |
|------|------|
| `GET /api/me/characters` | 我的角色列表（含 current_id 标记、每张卡的计算值） |
| `POST /api/me/characters` | 创建角色（body=完整 JSON，服务端 `finalize()` 重算后落盘） |
| `GET /api/me/characters/{id}` | 取单张卡（本人） |
| `PUT /api/me/characters/{id}` | 全量保存（`finalize()` 重算后落盘） |
| `DELETE /api/me/characters/{id}` | 删除（删除当前角色自动切换） |
| `POST /api/me/characters/{id}/activate` | 设为当前角色 |
| `GET /api/characters/{user_id}/{char_id}` | 查看他人卡（须登录；目标 `char_public=false` → 403） |
| `GET /api/trpg/rules` | 规则数据（种族/职业/技能表/购点表），免登录，前端实时计算用，单数据源 |

统一设置端点：

| 端点 | 说明 |
|------|------|
| `GET /api/me/settings` | 返回 `{"privacy": {"char_public": bool}}` |
| `PUT /api/me/settings` | body 深合并写入 |

页面路由（仿现有 profile 系列）：

```
GET /profile/trpg           车卡管理页（列表 + 当前角色 + 新建/编辑入口）
GET /trpg/char/{uid}/{id}   查看页（只读；他人卡受隐私开关约束）
```

## 前端页面

### `/profile/trpg` 车卡管理页（`trpg.html` + `trpg.js`）

- 顶部导航新增「跑团」入口（登录后可见）
- 角色列表区：每张卡一行（名称/种族/职业/Lv + "当前"标记），操作：新建 / 激活 / 编辑 / 删除（删除弹确认框）
- 点击新建或编辑 → 同页切换至单页分区表格编辑器：
  - 基本信息区：姓名 / 种族 / 职业 / 等级 / 背景 / 备注
  - 属性区：6 属性输入框，加值实时显示
  - 技能区：18 技能表格 [技能名 | 关联属性 | 熟练勾选 | 加值]，加值 = 属性加值 + 熟练 +2，实时算
  - 战斗区：HP / AC（职业 HP 骰 + 体质/敏捷加值实时提示，可手动覆盖）
  - 保存：整卡 JSON `PUT`，服务端重算返回，前端刷新显示计算值
- 规则数据来自 `GET /api/trpg/rules`（单数据源，不内嵌静态副本）

### `/trpg/char/{uid}/{id}` 查看页（`char_view.html` + `char_view.js`）

- 只读渲染同一套分区布局
- 他人卡且 `char_public=false` → 显示"对方未公开角色卡"
- 未登录 → 跳转登录

### 设置页隐私区块

现有 `settings.html` 增加「隐私设置」区：「允许他人查看我的角色卡」开关，读写 `/api/me/settings`。称号区块不动。

## QQ 端改动（`plugins/trpg_char`）

`/角色` 命令精简：

| 指令 | 现状 → 改动 |
|------|------------|
| `/角色` / `/角色 查看` | 仅查看自己的当前卡；移除 @ 他人支持 |
| `/角色 列表` | 保留，改读 `core.character_store` |
| `/角色 切换 <编号>` | 保留，改读新存储层 |
| `/角色 删除 <编号>` | 保留，改读新存储层 |
| `/角色 创建` | 废弃 → 回复引导"角色卡请到网页端填写：<地址>/profile/trpg" |
| `/角色 编辑 <字段> <值>` | 废弃 → 同上 |
| `/角色 放弃` | 废弃（向导删除，无进行中状态） |

删除：`wizard.py`、`_handle_wizard_reply`、`character_wizards` 运行时状态、`_handle_create/_handle_edit`。

其他消费方适配：

- `plugins/trpg_dice/__init__.py:109`：`dbmanager.character.current(user_id)` → `character_store.get_current(user_id)`；`resolve_expression_values` 逻辑不变（标准键契约保留）
- `plugins/trpg_session/__init__.py:273`：导出记录取角色名 → 换新存储层

同步维护（同 commit，按 AGENTS.md）：`plugins/menu/bot_menu_text.py`（角色命令文案）、`specs/`（数据库/插件目录/网页图库文档）、`KNOWLEDGE_BASE.md`。

## 错误处理

| 场景 | 行为 |
|------|------|
| 未登录访问 API | 401（现有鉴权） |
| 查看他人卡且隐私关闭 | 403 |
| 非法角色 JSON（缺标准键/属性越界） | 400 + 具体字段提示 |
| 文件读写异常 | 500 + `logger.exception`；原子写保证失败不损坏原文件 |
| 网页保存失败 | 前端保留已填内容，提示重试 |
| 删除角色 | 网页端弹确认框；QQ 端已有确认语义 |

## 测试

- `test/test_character_store.py`：存储层 CRUD 单测（创建/列表/切换/删除/越权路径/原子写/删除当前角色自动切换），`python test/test_character_store.py` 运行
- `test/test_trpg.py` 现有骰子测试保持通过（标准键契约未变）
- 手测清单：网页车卡全流程（新建→保存→刷新→切换→删除）、他人视角隐私开关（开/关）、QQ `/角色 查看/列表/切换/删除`、`.r 力量` / `.r 侦查+10` 骰子引用
