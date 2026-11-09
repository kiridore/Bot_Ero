"""防止新增直接私聊发送文件漏出黑名单核查清单。"""
import ast
from pathlib import Path


def test_private_sending_files_are_audited():
    root = Path(__file__).resolve().parents[1]
    change = root / 'openspec/changes/blacklist-management'
    if not change.exists():
        change = sorted((root / 'openspec/changes/archive').glob('*-blacklist-management'))[-1]
    inventory = (change / 'call-inventory.md').read_text(encoding='utf-8')
    for path in (root / 'plugins').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            direct = node.func.attr == 'send_private_msg'
            generic = (node.func.attr == 'call_api' and node.args
                       and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'send_private_msg')
            if direct or generic:
                assert f'| {path.relative_to(root).as_posix()} |' in inventory, path
