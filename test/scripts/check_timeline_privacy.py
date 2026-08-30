"""时间线打卡隐私读侧行为测试：私聊打卡按作者设置对他人隐藏（作者自见 + self_only）、
打卡图片按作者设置对他人高斯模糊（blur=1 URL 改写 + /thumb?blur=1 端点）、
feed/poll/new 三端点同口径过滤、含隐藏事件的 keyset 分页推进；
四态化（show/blur/text/hidden 按打卡类型）：text 剥图 + images_hidden、
blur/hidden 按事件类型独立生效、群聊 hidden 三端点过滤 + 作者自见。

独立进程运行: python test/scripts/check_timeline_privacy.py（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 必须在 import core.config / webapp 之前重定向 DB、用户设置、图片与缓存目录
_tmp = tempfile.mkdtemp(prefix="botero_timeline_privacy_test_")
_db = os.path.join(_tmp, "test.db")
os.environ["BOTERO_DB_PATH"] = _db
os.environ["BOTERO_USER_SETTINGS_ROOT"] = os.path.join(_tmp, "user_settings")
os.environ["BOTERO_IMAGE_ROOT"] = os.path.join(_tmp, "record_images")
os.environ["BOTERO_THUMB_CACHE"] = os.path.join(_tmp, "thumb_cache")
# 昵称解析立即失败降级（uid 直返），避免 192.168.x 超时拖慢测试
os.environ["BOTERO_ONEBOT_HTTP"] = "http://127.0.0.1:1"
os.environ["BOTERO_EVENT_TOKEN"] = "test-timeline-token"

_conn = sqlite3.connect(_db)
_cur = _conn.cursor()
from core.database_manager import init_schema  # noqa: E402
init_schema(_conn, _cur)
_conn.commit()

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from core import user_settings  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.config import IMAGE_ROOT, THUMB_CACHE_DIR  # noqa: E402
from webapp.app import app  # noqa: E402

A = "1057613133"  # 作者：私聊打卡隐藏 + 图片模糊
C = "3915014383"  # 普通查看者（设置全默认公开）
AH = {"Authorization": "Bearer " + make_login_key(int(A)), "Content-Type": "application/json"}
CH = {"Authorization": "Bearer " + make_login_key(int(C)), "Content-Type": "application/json"}

client = TestClient(app)
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def insert_event(eid, actor_qq, received_at, data=None, dedup_key=None):
    """直接造数（确定 received_at；data 传 dict 自动序列化）。"""
    _conn.execute(
        "INSERT OR IGNORE INTO timeline_events"
        " (id, source, received_at, actor_id, actor_qq, target_type, target_url,"
        " title, description, data, dedup_key)"
        " VALUES (?, 'checkin', ?, ?, ?, NULL, NULL, ?, NULL, ?, ?)",
        (eid, received_at, actor_qq, actor_qq, "{id:%s} 完成打卡" % actor_qq,
         json.dumps(data, ensure_ascii=False) if data is not None else None, dedup_key),
    )
    _conn.commit()


def feed_ids(headers, **params):
    r = client.get("/api/timeline", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return {e["id"]: e for e in r.json()["events"]}


# —— 种设置：A 关闭私聊打卡公开 + 关闭图片清晰公开 ——
user_settings.update_settings(A, {"privacy": {
    "private_checkin_public": False,
    "checkin_image_public": False,
}})

# —— 种真实图片（供 /thumb 与 ?blur=1 端点）——
img_folder = IMAGE_ROOT / A
img_folder.mkdir(parents=True, exist_ok=True)
src_jpg = img_folder / "img1.jpg"
im = Image.new("RGB", (600, 400))
for x in range(0, 600, 20):  # 高频条纹：模糊前后字节必然不同
    for y in range(400):
        im.putpixel((x, y), (0, 0, 0))
im.save(src_jpg, "JPEG", quality=90)
THUMB_URL = "/thumb/%s/img1.jpg" % A

# —— 种事件（received_at 递增，feed 序 = 新→旧）——
insert_event("checkin:a-priv", A, "2026-08-20 09:00:01",
             data={"private": True, "images": [THUMB_URL]}, dedup_key="p1")
insert_event("checkin:a-group", A, "2026-08-20 09:00:02",
             data={"images": [THUMB_URL]}, dedup_key="p2")
insert_event("checkin:c-ev", C, "2026-08-20 09:00:03",
             data={"images": ["/thumb/%s/x1.jpg" % C, "/thumb/%s/x2.jpg" % C]}, dedup_key="p3")

# —— 1. 查看者 C 的 feed：隐藏私聊 / 保留群聊 / A 的图片模糊 ——
evs = feed_ids(CH)
check("C 看不到 A 的私聊打卡", "checkin:a-priv" not in evs, str(sorted(evs)))
check("C 看得到 A 的群聊打卡", "checkin:a-group" in evs)
check("C 看得到自己的打卡", "checkin:c-ev" in evs)
a_group = evs.get("checkin:a-group") or {}
check("C 视角 A 的图片带 blur=1",
      any("blur=1" in u for u in (a_group.get("data") or {}).get("images", [])),
      str(a_group.get("data")))
c_ev = evs.get("checkin:c-ev") or {}
check("C 自己的图片不带 blur=1",
      not any("blur=1" in u for u in (c_ev.get("data") or {}).get("images", [])))
check("C 视角无 self_only 事件", not any(e.get("self_only") for e in evs.values()))

# —— 2. 作者 A 的 feed：私聊打卡自见 + self_only + 原图 ——
evs = feed_ids(AH)
a_priv = evs.get("checkin:a-priv")
check("A 看得到自己的私聊打卡", a_priv is not None)
check("A 的私聊打卡带 self_only=true", bool(a_priv and a_priv.get("self_only") is True), str(a_priv))
check("A 自己图片无 blur=1",
      not any("blur=1" in u for u in ((a_priv or {}).get("data") or {}).get("images", [])))
check("A 的群聊打卡无 self_only",
      not (evs.get("checkin:a-group") or {}).get("self_only"))

# —— 3. poll / new 同口径：C 的未读不含被隐藏事件 ——
# （C/A 的 watermark 已在上方首次 feed 时以当时 MAX(rowid) 初始化）
insert_event("checkin:a-priv2", A, "2026-08-20 10:00:01",
             data={"private": True, "images": []}, dedup_key="p4")
insert_event("checkin:c-new", C, "2026-08-20 10:00:02",
             data={"images": []}, dedup_key="p5")
r = client.get("/api/timeline/poll", headers=CH)
check("C poll 计数不含隐藏事件（=1）", r.json().get("count") == 1, r.text)
r = client.get("/api/timeline/new?limit=10", headers=CH)
new_ids = [e["id"] for e in r.json().get("events", [])]
check("C new 只含可见事件", new_ids == ["checkin:c-new"], str(new_ids))
insert_event("checkin:a-priv3", A, "2026-08-20 11:00:01",
             data={"private": True, "images": []}, dedup_key="p6")
r = client.get("/api/timeline/poll", headers=AH)
# A 水印在首次 feed 时初始化为当时 MAX(rowid)=3，此后 3 条插入（a-priv2/c-new/a-priv3）对 A 全部未读且全可见
check("A poll 计数含自己私聊打卡（=3）", r.json().get("count") == 3, r.text)
r = client.get("/api/timeline/new?limit=10", headers=AH)
new_a = r.json().get("events", [])
check("A new 含自己的私聊打卡且 self_only",
      [e["id"] for e in new_a] == ["checkin:a-priv3", "checkin:c-new", "checkin:a-priv2"]
      and all(e.get("self_only") is True for e in new_a if e["id"] != "checkin:c-new"),
      str(new_a))

# —— 4. /thumb?blur=1 端点：200 + 图片类型 + 字节不同 + 独立缓存文件 ——
r_plain = client.get(THUMB_URL, headers=CH)
r_blur = client.get(THUMB_URL + "?blur=1", headers=CH)
check("缩略图 200", r_plain.status_code == 200 and r_plain.headers["content-type"].startswith("image/"))
check("模糊图 200 且为图片", r_blur.status_code == 200 and r_blur.headers["content-type"].startswith("image/"))
check("模糊图字节与原图不同", r_plain.content != r_blur.content,
      f"plain={len(r_plain.content)}B blur={len(r_blur.content)}B")
blur_files = [p.name for p in THUMB_CACHE_DIR.glob("blur-*")] if THUMB_CACHE_DIR.is_dir() else []
check("模糊缓存独立文件 blur-*", bool(blur_files), str(blur_files))

# —— 5. 含隐藏事件的 keyset 分页：cursor 跨过隐藏行正确推进 ——
# C 可见序（新→旧）：c-new, c-ev, a-group；隐藏穿插：a-priv3, a-priv2, a-priv
page1 = client.get("/api/timeline", headers=CH, params={"limit": 1}).json()
check("C 分页第 1 页取最新可见事件",
      [e["id"] for e in page1["events"]] == ["checkin:c-new"] and page1["next_cursor"], str(page1))
page2 = client.get("/api/timeline", headers=CH,
                   params={"limit": 1, "cursor": page1["next_cursor"]}).json()
check("C 分页第 2 页跨过隐藏 a-priv2 取 c-ev",
      [e["id"] for e in page2["events"]] == ["checkin:c-ev"], str(page2))
page3 = client.get("/api/timeline", headers=CH,
                   params={"limit": 1, "cursor": page2["next_cursor"]}).json()
check("C 分页第 3 页取 a-group（跨过 a-priv）",
      [e["id"] for e in page3["events"]] == ["checkin:a-group"], str(page3))

# —— 6. 全隐藏范围取尽：空页必须重置 has_more，不得 500（P1 回归）——
# 两条比既有事件更旧的隐藏私聊打卡，cursor 限只取它们；
# 修复前：第 1 批全被过滤且满批 → has_more=True，第 2 批空页 break 未重置 → batch[-1] IndexError → 500
insert_event("checkin:a-priv-old1", A, "2026-08-19 08:00:01", data={"private": True}, dedup_key="pold1")
insert_event("checkin:a-priv-old2", A, "2026-08-19 08:00:02", data={"private": True}, dedup_key="pold2")
r_all_hidden = client.get("/api/timeline", headers=CH,
                          params={"limit": 1, "cursor": "2026-08-20 09:00:01|checkin:a-priv"})
check("全隐藏范围返回 200（修复前 500）", r_all_hidden.status_code == 200, r_all_hidden.text[:200])
body_all_hidden = r_all_hidden.json()
check("全隐藏范围 events 为空且无续读游标",
      body_all_hidden["events"] == [] and body_all_hidden["next_cursor"] is None, str(body_all_hidden)[:200])

# —— 7. 四态显示：text 剥图 + images_hidden；blur 按类型；群聊 hidden 按类型 ——
B = "1122334455"  # 新作者：直接用新四态键（不掺入旧键迁移场景）
BH = {"Authorization": "Bearer " + make_login_key(int(B)), "Content-Type": "application/json"}
insert_event("checkin:b-priv", B, "2026-08-21 09:00:01",
             data={"private": True, "images": ["/thumb/%s/bp1.jpg" % B]}, dedup_key="q1")
insert_event("checkin:b-group", B, "2026-08-21 09:00:02",
             data={"images": ["/thumb/%s/bg1.jpg" % B, "/thumb/%s/bg2.jpg" % B]}, dedup_key="q2")
user_settings.update_settings(B, {"privacy": {
    "checkin_display_private": "text",
    "checkin_display_group": "blur",
}})

evss = feed_ids(CH)
b_priv = evss.get("checkin:b-priv") or {}
check("text 态：C 可见 B 私聊打卡", "checkin:b-priv" in evss)
check("text 态：C 视角图片被剥离", (b_priv.get("data") or {}).get("images") == [], str(b_priv.get("data")))
check("text 态：事件带 images_hidden=true", b_priv.get("images_hidden") is True, str(b_priv)[:160])
check("text 态：无 self_only", not b_priv.get("self_only"))
b_group = evss.get("checkin:b-group") or {}
b_imgs = (b_group.get("data") or {}).get("images") or []
check("blur 态按类型：C 视角 B 群聊图全带 blur=1",
      bool(b_imgs) and all("blur=1" in u for u in b_imgs), str(b_imgs))
check("blur 态不产生 images_hidden", "images_hidden" not in b_group)

evss = feed_ids(BH)
b_priv = evss.get("checkin:b-priv") or {}
check("作者自见：B 私聊打卡原图",
      (b_priv.get("data") or {}).get("images") == ["/thumb/%s/bp1.jpg" % B], str(b_priv.get("data")))
check("作者自见：无 blur/无 images_hidden/无 self_only",
      "images_hidden" not in b_priv and not b_priv.get("self_only"))
b_group = evss.get("checkin:b-group") or {}
check("作者自见：B 群聊打卡原图无 blur",
      (b_group.get("data") or {}).get("images") == ["/thumb/%s/bg1.jpg" % B, "/thumb/%s/bg2.jpg" % B])

# 群聊 hidden：feed/new 对他人过滤 + 作者自见 self_only
user_settings.update_settings(B, {"privacy": {"checkin_display_group": "hidden"}})
insert_event("checkin:b-group2", B, "2026-08-21 10:00:01", data={"images": []}, dedup_key="q3")
evss = feed_ids(CH)
check("群聊 hidden：C 看不到 B 群聊打卡",
      "checkin:b-group" not in evss and "checkin:b-group2" not in evss)
new_ids = [e["id"] for e in client.get("/api/timeline/new?limit=50", headers=CH).json().get("events", [])]
check("群聊 hidden：C new 不含 B 群聊打卡",
      "checkin:b-group" not in new_ids and "checkin:b-group2" not in new_ids, str(new_ids))
evss = feed_ids(BH)
check("群聊 hidden：B 自见群聊打卡带 self_only",
      bool((evss.get("checkin:b-group") or {}).get("self_only"))
      and bool((evss.get("checkin:b-group2") or {}).get("self_only")))

# poll 差分：群聊从 hidden → show，计数恰增 2（b-group/b-group2 均未读无回执）
count_hidden = client.get("/api/timeline/poll", headers=CH).json().get("count")
user_settings.update_settings(B, {"privacy": {"checkin_display_group": "show"}})
count_show = client.get("/api/timeline/poll", headers=CH).json().get("count")
check("群聊 hidden 影响 poll 计数（差分=2）", count_show == count_hidden + 2,
      f"hidden={count_hidden} show={count_show}")

# —— 8. text 态守卫：无图事件不产生 images_hidden 角标（P2 回归）——
user_settings.update_settings(B, {"privacy": {"checkin_display_group": "text"}})
insert_event("checkin:b-group3", B, "2026-08-21 10:00:02", data={"images": []}, dedup_key="q4")
evss = feed_ids(CH)
b_g3 = evss.get("checkin:b-group3") or {}
check("text 态无图事件：C 可见且无 images_hidden 标记",
      "checkin:b-group3" in evss and "images_hidden" not in b_g3, str(b_g3)[:160])
check("text 态无图事件：data 不被改写",
      (b_g3.get("data") or {}).get("images") == [], str(b_g3.get("data")))

_conn.close()
print()
print("PASS" if fail == 0 else f"{fail} FAILURES")
raise SystemExit(1 if fail else 0)
