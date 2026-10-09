# Tasks

## 1. 表与数据层

- [x] 1.1 `core/db/_base.py::init_schema` 增加 4 张表 DDL（含 group_requests.flag 唯一索引），二次执行幂等（AC1、AC5）
- [x] 1.2 新建 `core/db/community.py::CommunityManager`（design 全部方法），`DbManager` 挂 `self.community`（AC1）
- [x] 1.3 `test/test_community_db.py`：spec 全部场景 + 幂等 + 挂载断言（AC1）

## 2. 文档与验收

- [x] 2.1 `kb/DATABASE.md`、`specs/database.md`：表数基线+4、四表结构/状态取值/索引说明（AC4）
- [x] 2.2 CHANGELOG `[未发布]` 记内部条目（不 bump，无用户可见变化）（AC4）
- [x] 2.3 全量 pytest 绿 + `openspec validate community-access-tables --strict` + 临时副本归档演练通过（AC2、AC3、AC5）
