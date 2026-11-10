"""跑团记录 Web API 回归：列表排序与状态、mine 过滤、坏目录跳过、详情增量、
暗骰过滤（AC10）、媒体路由与鉴权（AC05–AC07）。

独立进程运行: python test/scripts/check_trpg_records_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_trpg_records_api_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "images": os.path.join(_tmp, "record_images")},
    thumbs={"cache_dir": os.path.join(_tmp, "thumb_cache")},
)

from core import config  # noqa: E402
from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "12345601"
OTHER = "12345602"
BOT = str(config.BOT_QQ)
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
client = TestClient(app)
fail = 0

ROOT = Path(config.PYTHON_DATA_PATH) / "trpg_records"


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def msg(time, sender_type, user_id, nickname, char_name="", role="", segments=None, secret=False):
    entry = {
        "time": time, "sender_type": sender_type, "user_id": user_id,
        "nickname": nickname, "char_name": char_name, "role": role,
        "segments": segments or [],
    }
    if secret:
        entry["secret"] = True
    return entry


def write_record(group, start_dir, meta, messages=None, record_md=False, image=False):
    """直接写盘构造记录目录；messages 里的 str 行原样写入（用于构造半写坏行）。"""
    path = ROOT / group / start_dir
    (path / "imgs").mkdir(parents=True, exist_ok=True)
    (path / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if messages is not None:
        lines = [m if isinstance(m, str) else json.dumps(m, ensure_ascii=False) for m in messages]
        (path / "messages.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if image:
        (path / "imgs" / "img_0001.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    if record_md:
        (path / "record.md").write_text("# 跑团记录\n", encoding="utf-8")
    return path


def meta(group, group_name, start, end, participants, roles=None, rules="dnd5e"):
    return {
        "version": 2, "group_id": int(group), "group_name": group_name,
        "start": start, "end": end, "roles": roles or {}, "participants": participants,
        "rules": rules,
    }


# —— 夹具：三种状态 + 各类应被跳过的坏目录 ——
write_record(
    "800001", "2026-11-10_20-00-00",
    meta("800001", "夜航团", "2026-11-10 20:00:00", "2026-11-10 23:10:00", [
        {"user_id": ME, "nickname": "老张", "char_name": "艾拉", "role": "dm"},
        {"user_id": OTHER, "nickname": "小王", "char_name": "", "role": ""},
    ], {"111": "dm"}),
    [
        msg(1762776000, "user", ME, "老张", "艾拉", "dm", [{"type": "text", "text": "我推开酒馆的门"}]),
        msg(1762776031, "bot", BOT, "小埃", segments=[{"type": "text", "text": "老张的感知检定: D20=13=13"}]),
        msg(1762776040, "bot", BOT, "小埃", segments=[{"type": "text", "text": "暗骰：老张的D20=7=7"}], secret=True),
        msg(1762776050, "user", OTHER, "小王", segments=[{"type": "image", "local": "imgs/img_0001.jpg"}]),
        msg(1762776060, "user", OTHER, "小王", segments=[
            {"type": "at", "qq": ME}, {"type": "text", "text": "你看这里"}]),
        '{"time": 17627760',  # 半写坏行：读取时跳过且不抛异常
        msg(1762776070, "user", ME, "老张", "艾拉", "dm", [{"type": "text", "text": "损坏行之后照常返回"}]),
    ],
    record_md=True,
    image=True,
)
write_record(
    "800001", "2026-11-09_10-00-00",
    meta("800001", "夜航团", "2026-11-09 10:00:00", "2026-11-09 12:00:00", [
        {"user_id": ME, "nickname": "老张", "char_name": "艾拉", "role": ""},
    ], rules="coc7th"),
    [msg(1762653600, "user", ME, "老张", segments=[{"type": "text", "text": "上一场"}])],
)
write_record(
    "800002", "2026-11-11_09-00-00",
    meta("800002", "", "2026-11-11 09:00:00", None, [
        {"user_id": OTHER, "nickname": "小王", "char_name": "", "role": ""},
    ]),
    [msg(1762813200, "user", OTHER, "小王", segments=[{"type": "text", "text": "开场"}])],
)
# 坏目录：非法开始时间目录名、旧格式（version 1）、缺 messages.jsonl、非法群号目录
write_record("800003", "not-a-record",
             meta("800003", "坏目录", "2026-11-12 00:00:00", None, []), [])
write_record("800004", "2026-11-12_00-00-00",
             {"version": 1, "group_id": 800004, "group_name": "旧格式", "start": "2026-11-12 00:00:00",
              "end": None, "roles": {}, "participants": []},
             [msg(1762862400, "user", ME, "老张", segments=[{"type": "text", "text": "旧"}])])
write_record("800005", "2026-11-13_00-00-00",
             meta("800005", "缺消息文件", "2026-11-13 00:00:00", None, []), messages=None)
write_record("abc", "2026-11-14_00-00-00",
             meta("0", "非法群号", "2026-11-14 00:00:00", None, []),
             [msg(1762948800, "user", ME, "老张", segments=[{"type": "text", "text": "非法群号"}])])

EXPORTED = "2026-11-10_20-00-00"
ENDED = "2026-11-09_10-00-00"
RECORDING = "2026-11-11_09-00-00"

# —— 登录门控 ——
check("未登录列表 401", client.get("/api/trpg/records").status_code == 401)
check("未登录详情 401", client.get(f"/api/trpg/records/800001/{EXPORTED}").status_code == 401)
r = client.get(f"/trpg/media/800001/{EXPORTED}/img_0001.jpg")
check("未登录媒体 401（不是 302）", r.status_code == 401, str(r.status_code))

# —— AC05 列表：排序、三种状态、坏目录跳过、mine 过滤 ——
r = client.get("/api/trpg/records", headers=MH)
check("列表 200", r.status_code == 200)
items = r.json()["records"]
check("列表按开始时间倒序", [it["start_dir"] for it in items] == [RECORDING, EXPORTED, ENDED],
      str([it["start_dir"] for it in items]))
check("坏目录全部跳过", len(items) == 3)
by_dir = {it["start_dir"]: it for it in items}
check("已结束（有 record.md）状态", by_dir[EXPORTED]["state"] == "ended")
check("已结束（无 record.md）状态", by_dir[ENDED]["state"] == "ended")
check("录制中状态", by_dir[RECORDING]["state"] == "recording")
check("坏行不计入条数", by_dir[EXPORTED]["message_count"] == 6, str(by_dir[EXPORTED]["message_count"]))
check("最后消息时间取最后一条有效行", by_dir[EXPORTED]["last_message_at"] == 1762776070)
check("群名返回", by_dir[EXPORTED]["group_name"] == "夜航团")
check("群名缺失返回空串", by_dir[RECORDING]["group_name"] == "")
check("参与人返回", [p["nickname"] for p in by_dir[EXPORTED]["participants"]] == ["老张", "小王"])
check("is_mine 判定", by_dir[EXPORTED]["is_mine"] is True and by_dir[RECORDING]["is_mine"] is False)
check("规则名展示", by_dir[EXPORTED]["rules_name"] == "DND 5E" and by_dir[ENDED]["rules_name"] == "COC 7th",
      f'{by_dir[EXPORTED]["rules_name"]}/{by_dir[ENDED]["rules_name"]}')
check("玩家数排除 DM/观察者", by_dir[EXPORTED]["player_count"] == 1, str(by_dir[EXPORTED]["player_count"]))
check("我的身份为 DM（带角色卡名）", by_dir[EXPORTED]["my_role"] == {"role": "dm", "char_name": "艾拉"},
      str(by_dir[EXPORTED]["my_role"]))
check("未参与的记录我的身份为空", by_dir[RECORDING]["my_role"] == {"role": "", "char_name": ""})
r = client.get("/api/trpg/records?mine=1", headers=MH)
mine_items = r.json()["records"]
check("mine=1 只返回我参加的", [it["start_dir"] for it in mine_items] == [EXPORTED, ENDED],
      str([it["start_dir"] for it in mine_items]))
check("mine=1 全部 is_mine", all(it["is_mine"] for it in mine_items))

# —— AC06 详情与增量 ——
r = client.get(f"/api/trpg/records/800001/{EXPORTED}", headers=MH)
check("详情 200", r.status_code == 200)
detail = r.json()
check("详情 meta", detail["group_name"] == "夜航团" and detail["start"] == "2026-11-10 20:00:00"
      and detail["end"] == "2026-11-10 23:10:00" and detail["state"] == "ended")
check("详情 total 含被过滤暗骰", detail["total"] == 6, str(detail["total"]))
check("默认不含暗骰", len(detail["messages"]) == 5 and not any(m.get("secret") for m in detail["messages"]))
check("坏行跳过后仍返回", detail["messages"][-1]["segments"][0]["text"] == "损坏行之后照常返回")
image_seg = next(seg for m in detail["messages"] for seg in m["segments"] if seg["type"] == "image")
check("图片段转 url", image_seg.get("url") == f"/trpg/media/800001/{EXPORTED}/img_0001.jpg", str(image_seg))
check("at 段保留 qq", detail["messages"][3]["segments"][0] == {"type": "at", "qq": ME})

r = client.get(f"/api/trpg/records/800001/{EXPORTED}?from=4", headers=MH)
tail = r.json()
check("from=4 只返回其后消息", tail["from"] == 4 and len(tail["messages"]) == 2)
check("from=4 首条即第 5 条", tail["messages"][0]["segments"][1]["text"] == "你看这里")
check("from 不改变 total", tail["total"] == 6)
r = client.get(f"/api/trpg/records/800001/{EXPORTED}?from=99", headers=MH)
check("from 越界返回空列表", r.json()["messages"] == [])
r = client.get(f"/api/trpg/records/800001/{EXPORTED}?from=2", headers=MH)
check("from=2 默认过滤掉暗骰仍计入 total",
      r.json()["total"] == 6 and len(r.json()["messages"]) == 3)

# —— AC10 暗骰开关 ——
r = client.get(f"/api/trpg/records/800001/{EXPORTED}?reveal=1", headers=MH)
reveal = r.json()
secrets = [m for m in reveal["messages"] if m.get("secret")]
check("reveal=1 返回暗骰", len(secrets) == 1 and "暗骰" in secrets[0]["segments"][0]["text"])
check("reveal=1 条数与 total 一致", len(reveal["messages"]) == reveal["total"] == 6)
check("普通消息不带 secret 标记",
      not any(m.get("secret") for m in reveal["messages"] if m is not secrets[0]))
r = client.get(f"/api/trpg/records/800001/{EXPORTED}?reveal=1&from=3", headers=MH)
check("reveal=1 增量位置稳定", r.json()["messages"][0]["segments"][0]["local"] == "imgs/img_0001.jpg")

# —— AC06 错误码 ——
check("记录不存在 404",
      client.get("/api/trpg/records/800001/2026-01-01_00-00-00", headers=MH).status_code == 404)
check("缺 messages.jsonl 404",
      client.get("/api/trpg/records/800005/2026-11-13_00-00-00", headers=MH).status_code == 404)
check("非法群号 400", client.get("/api/trpg/records/abc/2026-11-10_20-00-00", headers=MH).status_code == 400)
check("非法目录名 400", client.get("/api/trpg/records/800001/not-a-record", headers=MH).status_code == 400)

# —— AC07 媒体路由 ——
r = client.get(f"/trpg/media/800001/{EXPORTED}/img_0001.jpg", headers=MH)
check("媒体 200", r.status_code == 200)
check("媒体 content-type 为图片", r.headers["content-type"] == "image/jpeg", r.headers.get("content-type", ""))
check("媒体内容非空", r.content.startswith(b"\xff\xd8\xff"))
check("媒体文件不存在 404",
      client.get(f"/trpg/media/800001/{EXPORTED}/img_9999.jpg", headers=MH).status_code == 404)
check("非图片文件名 400",
      client.get(f"/trpg/media/800001/{EXPORTED}/meta.json", headers=MH).status_code == 400)
r = client.get(f"/trpg/media/800001/{EXPORTED}/..%2F..%2Fdata.db", headers=MH)
check("目录穿越被拒绝（400/404）", r.status_code in (400, 404), str(r.status_code))
check("目录穿越不返回库文件", b"SQLite format" not in r.content)
check("绝对路径文件名 400",
      client.get(f"/trpg/media/800001/{EXPORTED}/C%3A%5Cimg_0001.jpg", headers=MH).status_code == 400)
check("非法群号媒体 400",
      client.get(f"/trpg/media/abc/{EXPORTED}/img_0001.jpg", headers=MH).status_code == 400)
check("非法目录名媒体 400",
      client.get(f"/trpg/media/800001/not-a-record/img_0001.jpg", headers=MH).status_code == 400)

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
