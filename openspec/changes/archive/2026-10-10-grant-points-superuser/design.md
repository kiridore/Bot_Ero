# Design

单点改动：`plugins/grant_points_all/__init__.py:13` 的 `self.admin_user()` → `self.super_user()`。

- 匹配层拦截（match 返回 False）= 静默不响应，与该插件现有"无权限即无反应"行为一致。
- 不改 handle 内部（match 不过不会进 handle）。
- 文档两处权限描述同步；菜单条目已在仅超管可见段，无需变更。
