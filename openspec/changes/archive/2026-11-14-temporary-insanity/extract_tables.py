"""从规则书 PDF 抽取表Ⅸ恐惧症状表与表Ⅹ狂躁症状表（`core/trpg/madness.py` 的数据来源）。

用法：
    pdftotext -enc UTF-8 "docs/COC7th守密人核心规则书.pdf" /tmp/coc_kp.txt
    python openspec/changes/archive/2026-11-14-temporary-insanity/extract_tables.py

产出 /tmp/madness.json（phobias / manias 各 100 条），再据此生成 madness.py 的数据块。
"""

import json
import pathlib
import re

SOURCE = pathlib.Path("/tmp/coc_kp.txt")
OUTPUT = pathlib.Path("/tmp/madness.json")

text = SOURCE.read_text(encoding="utf-8", errors="replace")
p_start = text.index("表Ⅸ：恐惧症状表 恐惧症是对某些事物")
m_start = text.index("表Ⅹ：狂躁症状表 狂躁症会带来对某一事物")
m_end = text.index("疯狂的副作用 2", m_start)

FOOTNOTES = "①②③④⑤⑥⑦⑧⑨⑩"


def clean(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.isdigit() or s in ("第八章 理智", "Call of Cthulhu 7th Edition"):
            continue
        lines.append(s)
    return "".join(lines).replace("  ", "")


def parse(raw: str, head: str) -> list[dict]:
    body = clean(raw).split(head, 1)[1]
    body = re.sub(r"（原文\s*如此[^）]*）", "", body)   # 译者「存疑」说明
    body = re.sub(f"[{FOOTNOTES}]", "", body)          # 脚注标记 ①②
    parts = re.split(r"(?<!\d)(\d{1,3})\)\s*", body)
    items = []
    for i in range(1, len(parts) - 1, 2):
        num, body_text = int(parts[i]), parts[i + 1].strip()
        if not body_text:
            continue
        matched = re.match(r"^([^：:]+)[：:](.*)$", body_text, re.S)
        name_part, desc = ((matched.group(1).strip(), matched.group(2).strip())
                           if matched else (body_text, ""))
        latin = ""
        found = re.search(r"[（(]([A-Za-z][^）)]*)[）)]", name_part)
        if found:
            latin = found.group(1).strip()
            name_part = name_part[:found.start()].strip()
        items.append({"num": num, "name": name_part.replace("*", "").strip(),
                      "latin": latin, "description": desc})
    return items


phobias = parse(text[p_start:m_start], "表Ⅸ：恐惧症状表")
manias = parse(text[m_start:m_end], "表Ⅹ：狂躁症状表")
assert [i["num"] for i in phobias] == list(range(1, 101)), "恐惧表编号不连续"
assert [i["num"] for i in manias] == list(range(1, 101)), "狂躁表编号不连续"
assert all(i["name"] and i["latin"] and i["description"] for i in phobias + manias)

OUTPUT.write_text(json.dumps({"phobias": phobias, "manias": manias}, ensure_ascii=False, indent=1),
                  encoding="utf-8")
print(f"phobias={len(phobias)} manias={len(manias)} -> {OUTPUT}")
