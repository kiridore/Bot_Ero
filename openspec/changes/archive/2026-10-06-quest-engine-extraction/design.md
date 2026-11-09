# 设计 · 周常任务引擎迁出 core（T0.5）

## 搬家清单（函数体逐字不动）

| 符号 | 从 | 到 |
|---|---|---|
| `QUEST_DEFS`（6 任务表 + ponytail 注释） | `core/utils.py:118-126` | `plugins/weekly_quest/engine.py` |
| `get_quest_week_key()` | `core/utils.py:128` | 同上 |
| `on_quest_trigger(db, user_id, trigger_type)` | `core/utils.py:131-153` | 同上 |
| `on_quest_rollback(db, user_id, trigger_type)` | `core/utils.py:154-165` | 同上 |

engine.py 头部：`from core.utils import get_monday_to_monday, add_user_point`（plugins→core 合法绝对导入）。

## import 改造（5 处，已核对当前行号）

```python
# checkin/__init__.py:5
from core.utils import add_user_point, ensure_checkin_image, get_monday_to_monday
from plugins.weekly_quest.engine import on_quest_trigger
# lottery/__init__.py:7
from core.utils import register_plugin
from plugins.weekly_quest.engine import on_quest_trigger
# checkin_recall/__init__.py:6 / roll_back/__init__.py:4
from core.utils import get_monday_to_monday
from plugins.weekly_quest.engine import on_quest_rollback
# weekly_quest/__init__.py:3
from core.utils import register_plugin, get_monday_to_monday
from plugins.weekly_quest.engine import QUEST_DEFS, get_quest_week_key
```

**循环导入论证**：checkin → weekly_quest.engine 触发 weekly_quest 包 `__init__` 先执行 → 其只 import core.* 与 engine → 无回边。`python -c "import plugins"` 全量注册即验证。

## 测试策略（`test/test_quest_engine.py`）

conftest 临时 DB（零真实数据风险）；用真实 `DbManager` 走真实 quest/points/checkin 表：

1. `db.checkin.insert(uid, images=[], message_id=1001)`（本周内）→ `on_quest_trigger(db, uid, "checkin")` 断言 `completed == [{"name": "打个卡先", "reward": 1}]`（仅 goal=1 的任务 1 达标；任务 2/3 goal 3/7 未达）且 `db.points.get(uid)` 由 0 → 1
2. `db.checkin.delete_by_msg(uid, 1001)` → count 回 0 → `on_quest_rollback(db, uid, "checkin")` 断言 `revoked` 含任务 1、积分回 0
3. 新家地址断言：`plugins.weekly_quest.engine` 具备全部四符号（防 import 路径笔误）

## 风险

- 无行为风险：纯搬家，等价性由现有 387+ 用例回归证明
- engine.py 会被 `pkgutil.walk_packages` 导入一次——无插件类、无副作用，无害
