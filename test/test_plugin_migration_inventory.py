"""迁移清单覆盖所有当前发送文件；只解析代码，不导入插件或访问运行数据库。"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGE = ROOT / "openspec/changes/plugin-event-dispatch"
if not CHANGE.exists():
    # 验收通过后提案会归档；同一份清单仍须继续约束后续迁移。
    CHANGE = sorted((ROOT / "openspec/changes/archive").glob("*-plugin-event-dispatch"))[-1]


def sending_files():
    found = set()
    for path in (ROOT / "plugins").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            method = node.func.attr
            if (method.startswith("send_") or method == "submit_message"
                    or (method == "submit" and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == "output")):
                found.add(path.relative_to(ROOT).as_posix())
            if method == "call_api":
                assert node.args and isinstance(node.args[0], ast.Constant), (
                    f"动态 API 调用必须人工重新审计：{path}:{node.lineno}"
                )
                if str(node.args[0].value).startswith("send_"):
                    found.add(path.relative_to(ROOT).as_posix())
    return found


def test_all_sending_files_are_documented():
    inventory = (CHANGE / "migration.md").read_text(encoding="utf-8")
    missing = [path for path in sorted(sending_files()) if f"| {path} |" not in inventory]
    assert not missing, f"缺失发送文件及其迁移阶段：{missing}"


def test_wrapper_routes_and_non_message_operations_are_documented():
    inventory = (CHANGE / "migration.md").read_text(encoding="utf-8")
    for name in ("broadcast", "broadcast_vote_result", "send_forward_to_group", "_send_forward",
                 "_send_private", "_announce_group", "set_friend_add_request", "MessageLogManager"):
        assert name in inventory, name


def test_first_phase_does_not_use_obsolete_economy_gate():
    for folder in ("checkin", "checkin_recall", "roll_back", "lottery", "title", "weekly_quest", "redeem_shop"):
        for path in (ROOT / "plugins" / folder).rglob("*.py"):
            assert "economy_active" not in path.read_text(encoding="utf-8-sig"), path
