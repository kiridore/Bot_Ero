# DND 5E 角色卡插件设计

> 日期: 2026-07-31
> 状态: 已确认（设计评审通过）

## 背景

跑团功能包（trpg）已有骰子系统（trpg_dice，Sealdice 语法）和聊天记录（trpg_session）。现在新增角色卡系统，让用户能创建和管理 DND 5E 角色，并与骰子系统、聊天记录联动。

## 需求确认

| 项 | 结论 |
|----|------|
| 范围 | 完整角色卡管理（创建/查看/编辑/删除/切换） |
| 引导 | 对话式逐步引导（可中断，可放弃） |
| 规则数据 | PHB 核心：8种族、12职业、10背景、18技能 |
| 属性生成 | 购点27点 / 4d6k3掷骰 / 标准数组 三种 |
| 持久化 | 角色卡 SQLite，创建进度内存 |
| 骰子集成 | `.r 力量` / `.r 侦查+10` 属性引用 |
| 归属 | 全局共享 + 当前角色切换 |
| 字段 | 名字/种族/职业/等级/背景 + 6属性 + 技能熟练 + HP/AC + 初始装备 |
| 等级 | 初始 1 级，无升级功能 |
| 功能包 | 加入「跑团」包 + 导出记录显示角色名 |

## 指令集

| 指令 | 功能 |
|------|------|
| `/角色 创建` | 开始分步创建引导 |
| `/角色` 或 `/角色 查看` | 查看当前角色卡 |
| `/角色 查看 @用户` | 查看他人角色卡 |
| `/角色 编辑 <字段> <值>` | 修改角色卡单项（hp/ac/属性/装备等） |
| `/角色 切换 <编号>` | 切换当前使用哪个角色 |
| `/角色 列表` | 列出我的所有角色 |
| `/角色 删除 <编号>` | 删除角色（需回复确认） |
| `/角色 放弃` | 放弃当前进行中的创建 |
| `.r 力量` `.r 侦查+10` | 属性/技能引用（集成骰子） |

## 架构

单插件多文件：

```
plugins/trpg_char/
├── __init__.py     # 主插件：指令路由、引导入口
├── wizard.py       # 创建引导状态机（步骤定义、进度存储）
├── rules.py        # DND 5E 规则数据（种族/职业/背景/技能定义）
└── character.py    # 角色卡计算（属性加值、HP、AC、熟练加值）
```

## 数据模型

### DB 表（`core/db/_base.py` 的 init_schema 增加）

```sql
CREATE TABLE IF NOT EXISTS dnd_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    char_name TEXT NOT NULL,
    race TEXT NOT NULL,
    class_name TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    background TEXT NOT NULL,
    str_score INTEGER, dex_score INTEGER, con_score INTEGER,
    int_score INTEGER, wis_score INTEGER, cha_score INTEGER,
    proficient_skills TEXT,      -- JSON 数组
    hp INTEGER, ac INTEGER,
    equipment TEXT,              -- JSON 数组
    created_at TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS dnd_current_character (
    user_id TEXT PRIMARY KEY,
    character_id INTEGER NOT NULL
);
```

### 创建进度（`core/context.py` 内存）

```python
character_wizards: dict[int, dict] = {}  # user_id -> {step, data}
```

步骤推进: ①种族 → ②职业 → ③属性生成方式 → ④分配属性 → ⑤技能熟练 → ⑥背景 → ⑦角色名 → 完成

每步 bot 发送选项列表，用户回复编号或文字；「退出」中止并删除进度。

## 规则数据（rules.py）

| 数据 | 内容 |
|------|------|
| 8 种族 | 人类/精灵/矮人/半身人/半精灵/半兽人/龙裔/侏儒 + 属性加值 |
| 12 职业 | 战士/法师/游荡者/牧师/武僧/圣武士/游侠/德鲁伊/术士/吟游诗人/野蛮人/邪术师 + HP骰 + 熟练技能数 |
| 10 背景 | 侍僧/罪犯/艺人/民间英雄/贵族/流浪儿/贤者/水手/士兵/苦工 + 技能 |
| 18 技能 | 运动/杂技/巧手/隐秘/奥术/历史/调查/自然/宗教/驯兽/洞悉/威吓/医药/洞察/游说/欺瞒/表演/生存 |

## 属性生成

- **标准购点（27点）**：购点成本表 8=0, 9=1, 10=2, 11=3, 12=4, 13=5, 14=7, 15=9
- **4d6k3 掷骰**：bot 掷 6 组属性，用户分配到 6 项属性
- **标准数组**：15, 14, 13, 12, 10, 8 分配到 6 项属性

## 计算规则

- 属性加值 = `(score - 10) // 2`
- 初始 HP = HP骰最大值 + 体质加值（1级）
- 初始 AC = 10 + 敏捷加值（本版本不区分护甲类型，职业默认装备后续扩展）
- 技能加值 = 属性加值 + (熟练加成 2 if 熟练 else 0)
- 初始装备 = 职业默认装备列表（存 JSON）

## 骰子集成（改 trpg_dice/__init__.py）

`.r` 预处理：tokenize 前将已知属性名/技能名替换为角色卡数值。

```
.r 力量      → 力量加值（如 3）
.r 侦查+10   → 技能加值（如 3）+ 10
```

查当前用户 `dnd_current_character`，未创建角色则提示先创建。

## 记录联动（改 trpg_session/__init__.py）

导出 record.md 时发言者显示 `角色名(昵称)`，从 `dnd_current_character` 查发送者的当前角色。无角色时保持 `昵称`。

## 功能包

- `core/feature_packs.py` 跑团包加 `"trpg_char"`
- `core/context.py` `RECORDING_ALLOWED_PLUGINS` 加 `"trpg_char"`

## 边界情况

| 场景 | 行为 |
|------|------|
| 创建中再发 `/角色 创建` | 提示已有进行中的创建，或回复「退出」后重新开始 |
| 创建中收到非引导消息 | 忽略并提示当前步骤 |
| 删除当前角色 | 清除当前角色指向，若还有其他角色则自动切换 |
| 无角色时 `.r 力量` | 提示先创建角色 |
| 私聊使用 | 允许（角色卡全局共享，私聊也可管理） |
| 引导超时 | 无超时机制，用户可随时「退出」 |

## 测试

`test/test_trpg_char.py`：
- 规则数据完整性（8种族/12职业/10背景/18技能）
- 属性计算（加值/HP/AC/技能加值）
- 引导状态机步骤推进与放弃
- 三种属性生成方式
- 角色 CRUD + 当前角色切换
- 骰子属性替换预处理
