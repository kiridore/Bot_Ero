"""把并行整理的分片合并成 core/trpg/occupation_skills.json（数据管线，可重跑）。

规范化规则见 proposal.md 的「数据裁定」：
- `类别:任一` / `类别:任意` / 裸类别名 → `类别:*`
- 去重、去掉空的可选池
- 每个 seq 必须落在 2..114，技能名必须可对上技能表
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent.parent
sys.path.insert(0, str(PROJECT))

CANON = json.loads((ROOT / "canonical_skills.json").read_text(encoding="utf-8"))
SKILLS = set(CANON["skills"])
CATEGORIES = set(CANON["categories"])
TARGET = PROJECT / "core" / "trpg" / "occupation_skills.json"


def normalize(name: str) -> str:
    raw = str(name or "").strip().rstrip("。，、；;")
    if not raw:
        return ""
    if raw in SKILLS:
        return raw
    if ":" in raw or "：" in raw:
        head, _, tail = raw.replace("：", ":").partition(":")
        head = head.strip()
        tail = tail.strip()
        if head in CATEGORIES:
            if tail in ("任一", "任意", "*", ""):
                return f"{head}:*"
            return f"{head}:{tail}"
        return ""
    if raw in CATEGORIES:
        return f"{raw}:*"
    return ""


def merge() -> dict:
    merged = {"1": {"required": [], "choices": [{"count": 8, "from": "*"}]}}
    problems = []
    for part in sorted((ROOT / "parts").glob("part*.json")):
        data = json.loads(part.read_text(encoding="utf-8"))
        for seq, entry in data.items():
            required = []
            for name in entry.get("required") or []:
                fixed = normalize(name)
                if not fixed:
                    problems.append((part.name, seq, "required", name))
                elif fixed not in required:
                    required.append(fixed)
            choices = []
            for choice in entry.get("choices") or []:
                count = int(choice.get("count") or 0)
                source = choice.get("from")
                if count <= 0:
                    continue
                if source == "*":
                    choices.append({"count": count, "from": "*"})
                    continue
                pool = []
                for name in source or []:
                    fixed = normalize(name)
                    if not fixed:
                        problems.append((part.name, seq, "from", name))
                    elif fixed not in pool:
                        pool.append(fixed)
                if pool:
                    choices.append({"count": count, "from": pool})
            merged[seq] = {"required": required, "choices": choices}
    return merged, problems


if __name__ == "__main__":
    merged, problems = merge()
    missing = [str(s) for s in range(2, 115) if str(s) not in merged]
    if problems or missing:
        print("未通过：")
        for item in problems[:20]:
            print("  表外技能名", item)
        if missing:
            print("  缺少 seq", missing)
        sys.exit(1)
    ordered = {str(k): merged[str(k)] for k in sorted(int(x) for x in merged)}
    TARGET.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"已写入 {TARGET}：{len(ordered)} 个职业")
