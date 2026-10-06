# 文案包加载机制（社区版 T0.8 · 设计变更）

> **设计变更（2026-10-06 所有者拍板，四问全锁推荐）**：T0.8 原"菜单双文本（COMMUNITY_MENU_TEXT 常量按 edition 切换）"改为**文案外置包机制**——文案提取为配置文件，启动时按 `bot.text_pack` 加载不同包载入不同文案。范围：菜单/指令帮助文案（现 `bot_menu_text.py` 全部内容）。

## Why

社区版与私有版的文案差异不应固化在代码常量里（每套文案一次编译期分支）；外置成包后：社区部署 = config 指针指向 `text_packs/community.yaml`，私有部署 = 不配该键 = 内置文案原样（零变化）。机制对未来文案单元（M1 注册引导语、T2.4 运营物料）天然可扩展——加键即可，不再动代码。

## What Changes

- **`core/config.py`**：新键 `bot.text_pack`（缺省空串 = 不加载任何包）
- **新 `core/text_pack.py`**：启动时一次性加载包 yaml 到内存 dict；`get_text(key, default)` 缺键/空值回落 default；包内 `{NICKNAME}` 占位符替换；包缺失/非法/顶层非映射 → WARNING 日志 + 回落内置，绝不崩溃
- **`plugins/menu/__init__.py`**：`handle()` 改为 `get_text("menu_text", BOT_MENU_TEXT)`（惰性求值，无模块级绑定——热改包不需 reload，测试免 reload）
- **`bot_menu_text.py` 不动**：继续作为内置基线（≡ 私有现状文案），也是"指令文本唯一来源"惯例的锚点
- **新 `text_packs/community.yaml`**：社区中性文案**草稿**（Q4:A——去 板油/FF14/"喵"人设；指令集 = 打卡基础+经济扩展两包 + 管理员指令；T2.4 定稿）
- **不 ship `text_packs/private.yaml`**：内置基线即私有文案，双份存储只会漂移（设计要点，见 design）
- `config.example.yaml` 补 `text_pack` 键注释

**Ruling（版本记录）**：部署者面能力 + 私有行为零变化，按 T0.4（system_plugins）/Docker/mail.proxy 先例记 CHANGELOG `[未发布]` 不 bump。

## Capabilities

- **New Capabilities**：`text-packs`——文案包的加载、覆盖与回退契约
- **Modified Capabilities**：无

## 验收标准

1. **私有零变化**：不配 `bot.text_pack` 时 `/菜单` 输出与现状 `BOT_MENU_TEXT` 逐字节一致；全量 pytest 绿（红线 #122）
2. **包覆盖生效**：包含非空 `menu_text` 键 → `get_text("menu_text", BOT_MENU_TEXT)` 返回包文本，其中 `{NICKNAME}` 被替换为配置昵称
3. **缺键回落**：包存在但无 `menu_text` 键（或值为空串/null/非字符串）→ 返回内置默认
4. **坏包不崩**：包路径不存在 / yaml 语法错 / 顶层非映射 → 记 WARNING、`get_text` 返回默认，进程正常启动
5. **社区包可用**：`text_packs/community.yaml` 为合法 yaml、含 `menu_text`、不含"FF14/喵"字样；"板油"仅允许作为既有触发词出现（`/本周板油` 描述已中性化为"查看本周打卡成员"——触发词改名是独立任务，不在本提案范围；验收措辞自"不含板油字样"修订，Ruling 记录）、`{NICKNAME}` 占位符存在
6. **文档同步**：AGENTS.md 菜单文本条目、specs/conventions.md §双形态接缝措辞、kb/QUICK_REFERENCE.md、development-plan T0.8 节按新设计改写
