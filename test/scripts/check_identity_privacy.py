"""网站身份读取回归：全部展示面、历史姓名、周报兼容；独立临时配置与模拟 OneBot。"""

import json
import os
import sys
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _env import write_config

_tmp = tempfile.TemporaryDirectory(prefix="botero_identity_privacy_", ignore_cleanup_errors=True)
os.environ["BOTERO_CONFIG"] = write_config(_tmp.name, timeline={"url": "", "token": ""})

from core import character_store, onebot_client, user_settings
from core.auth import make_login_key
from core.config import GROUP_ID
from core.database_manager import DbManager
from fastapi.testclient import TestClient

A, B = "111111", "222222"
ANON = user_settings.anonymous_name(A)


def real(uid):
    return "真实昵称" + str(uid)


def avatar(uid):
    return "https://example.test/avatar/" + str(uid)


# 在路由导入前模拟共享解析器；任何意外 requests 网络请求都立即失败。
with patch.object(onebot_client, "resolve_display_name", side_effect=real), \
     patch.object(onebot_client, "resolve_avatar_url", side_effect=avatar), \
     patch("requests.sessions.Session.request", side_effect=AssertionError("测试禁止真实网络")):
    from webapp.app import app
    from webapp.live import app as live
    from webapp.weekly.app import _display_report

    db = DbManager()
    for uid in (A, B):
        db.timeline.get_or_init_watermark(uid)
    post_id = db.forum.create_post(A, "post", "保留正文", json.dumps({"type": "doc", "content": []}))
    root = db.forum.create_comment(post_id, B, "正文提到" + real(A))
    reply = db.forum.create_comment(post_id, A, "不改用户正文", parent_id=root["id"])
    db.forum.create_comment(post_id, B, "回复作者", parent_id=reply["id"])
    activity_id = db.activity.create_activity(GROUP_ID, "collect", "活动", "", A)
    for uid in (A, B):
        db.activity.add_member(activity_id, uid, "旧昵称" + uid)
        db.tools.add_tool(uid, "工具" + uid, "用户正文" + real(A), "https://example.test/" + uid, "example.test")
        db.cur.execute(
            "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
            (uid, "2026-08-20 09:00:00", "image" + uid),
        )
        db.cur.execute(
            "INSERT INTO timeline_events (id, source, received_at, actor_id, actor_qq, title, description)"
            " VALUES (?, 'test', ?, ?, ?, ?, ?)",
            ("identity:" + uid, "2026-08-20 09:00:00", uid, uid, "作者{id:" + uid + "}", "引用{id:" + A + "}"),
        )
    db.conn.commit()
    fire = datetime(2099, 1, 10, 8)
    for uid in (A, B):
        db.alarm.add(int(uid), fire, "提醒" + uid, group_id=int(GROUP_ID), is_private=False)
    char_data = {"char_name": "角色不是昵称", "race": "人类", "class_name": "战士", "level": 1,
                 **{key + "_score": 10 for key in ("str", "dex", "con", "int", "wis", "cha")}}
    char_id = character_store.create_char(A, char_data)
    report = {
        "period": {"issue": 1},
        "headline": {"kind": "immortal_jackpot", "title": "仙人彩大奖落定",
                     "body": "本期开奖号码 1234，旧昵称111111（1234）、旧昵称222222（1230） 命中大奖！",
                     "stats": [{"label": "开奖号码", "value": "1234"},
                               {"label": "大奖得主", "value": "旧昵称111111（1234）、旧昵称222222（1230）"},
                               {"label": "总奖池", "value": 99}]},
        "lottery": {"immortal": {"digits": "1234", "pool": 99, "winners": [
            {"user_id": int(A), "name": "旧昵称" + A, "digits": "1234", "tier": "一等奖(4A)"},
            {"user_id": int(B), "name": "旧昵称" + B, "digits": "1230", "tier": "二等奖(3A)"},
        ]}},
        "checkin": {"full_week": [{"user_id": int(A), "name": "旧昵称" + A}]},
        "voices": {"quotes": [{"user_id": int(A), "name": "旧昵称" + A, "text": "旧昵称111111 是用户原文"}]},
        "activity": {"talkers": [{"user_id": int(A), "name": "旧昵称" + A}]},
    }
    historical = {"user_id": int(A), "name": "旧昵称" + A}
    report["checkin"]["images"] = [{**historical, "url": "/thumb/111111/photo"}]
    report["lottery"].update(top=dict(historical), lucky=[dict(historical)], unlucky=dict(historical))
    report["voices"]["meme_king"] = dict(historical)
    report["activity"].update(night_owl=dict(historical), early_bird=dict(historical), new_titles=[dict(historical)])
    report["trivia"] = {key: [dict(historical)] for key in ("streaks", "gains", "records")}
    db.weekly.upsert("2026-08-17", int(GROUP_ID), report)

    with TestClient(app) as client:
        def get(url, viewer=A):
            response = client.get(url, headers={"Authorization": "Bearer " + make_login_key(viewer)})
            assert response.status_code == 200, (url, response.status_code, response.text)
            return response.json()

        def check_surfaces(viewer, hidden):
            name = ANON if hidden else real(A)
            old_name = ANON if hidden else "旧昵称" + A
            image = f"/identicon/{A}.png" if hidden else avatar(A)
            feed = get("/api/timeline", viewer)
            assert feed["users"][A] == {"name": name, "avatar": image}
            assert feed["users"][B] == {"name": real(B), "avatar": avatar(B)}
            events = {e["actor"]["qq"]: e for e in feed["events"]}
            assert events[A]["actor"]["display_name"] == name
            assert events[A]["actor"]["avatar_url"] == image
            assert events[B]["description"] == "引用{id:" + A + "}"
            newer = get("/api/timeline/new?after=1", viewer)
            assert newer["users"][A]["name"] == name
            for post in (get("/api/forum/posts", viewer)["items"][0], get(f"/api/forum/posts/{post_id}", viewer)):
                assert post["author_name"] == name and post["author_avatar"] == image
                assert post["author_user_id"] == A
            comments = get(f"/api/forum/posts/{post_id}/comments", viewer)["items"][0]
            assert comments["body_text"] == "正文提到" + real(A)
            assert comments["replies"][0]["author_name"] == name
            assert comments["replies"][0]["author_avatar"] == image
            assert comments["replies"][1]["reply_to_name"] == name
            assert comments["replies"][1]["reply_to_user_id"] == A
            options = {u["user_id"]: u["display_name"] for u in get("/api/users", viewer)["users"]}
            assert options == {A: name, B: real(B)}
            images = get(f"/api/checkins?only_with_file=false&user_id={A}", viewer)["items"]
            assert len(images) == 1 and images[0]["user_id"] == A and images[0]["display_name"] == name
            members = get(f"/api/activities/{activity_id}", viewer)["members"]
            assert members[0]["nickname"] == old_name and members[1]["nickname"] == "旧昵称" + B
            listed = next(item for item in get("/api/activities", viewer)["items"] if item["id"] == activity_id)
            assert listed["members"][0]["nickname"] == old_name
            assert listed["members"][1]["nickname"] == "旧昵称" + B
            assert db.activity.get_activity(activity_id)["members"][0]["nickname"] == "旧昵称" + A
            viewers = get("/api/live/viewers", viewer)["viewers"]
            assert {v["name"] for v in viewers} == {name, real(B)}
            alarms = get("/api/me/calendar?month=2099-01", viewer)["days"]["2099-01-10"]
            assert {a["content"]: a["creator_name"] for a in alarms} == {"提醒" + A: name, "提醒" + B: real(B)}
            tools = {t["created_by"]: t for t in get("/api/tools", viewer)["items"]}
            assert tools[A]["created_by_name"] == name and tools[A]["created_by_avatar"] == image
            assert tools[B]["created_by_name"] == real(B) and tools[B]["created_by_avatar"] == avatar(B)
            assert tools[A]["description"] == "用户正文" + real(A)
            char = get(f"/api/characters/{A}/{char_id}", viewer)
            assert char["display_name"] == name and char["char_name"] == "角色不是昵称"
            weekly = get("/api/weekly/2026-08-17", viewer)
            assert weekly["checkin"]["full_week"][0]["name"] == old_name
            identities = [weekly["checkin"]["images"][0], weekly["lottery"]["top"],
                          weekly["lottery"]["lucky"][0], weekly["lottery"]["unlucky"],
                          weekly["voices"]["meme_king"], weekly["activity"]["night_owl"],
                          weekly["activity"]["early_bird"], weekly["activity"]["new_titles"][0],
                          *(weekly["trivia"][key][0] for key in ("streaks", "gains", "records"))]
            assert all(item["name"] == old_name and item["user_id"] == int(A) for item in identities)
            assert weekly["voices"]["quotes"][0]["name"] == old_name
            assert weekly["voices"]["quotes"][0]["text"] == "旧昵称111111 是用户原文"
            assert weekly["activity"]["talkers"][0]["name"] == old_name
            assert weekly["lottery"]["immortal"]["winners"][0]["user_id"] == int(A)
            assert weekly["headline"]["body"] == f"本期开奖号码 1234，{old_name}（1234）、旧昵称222222（1230） 命中大奖！"
            assert weekly["headline"]["stats"][1]["value"] == f"{old_name}（1234）、旧昵称222222（1230）"
            if not hidden:
                assert weekly == report
            print("ok - 全部网站展示", viewer, "匿名" if hidden else "真实")

        for uid in (A, B):
            response = client.post("/api/live/heartbeat", json={"client_id": uid},
                                   headers={"Authorization": "Bearer " + make_login_key(uid)})
            assert response.status_code == 200
        check_surfaces(A, False)
        check_surfaces(B, False)
        user_settings.update_settings(A, {"privacy": {"identity_public": False}})
        check_surfaces(A, False)
        check_surfaces(B, True)
        # 不补心跳：现有 presence 仍是真名，读侧立即采用新设置。
        assert live._presence[A]["name"] == real(A)
        assert db.activity.get_activity(activity_id)["members"][0]["nickname"] == "旧昵称" + A
        assert db.weekly.get("2026-08-17", int(GROUP_ID))["data_json"] == report
        assert get("/api/me/characters")["characters"][0]["display_name"] == real(A)
        assert get(f"/api/me/characters/{char_id}")["display_name"] == real(A)
        for method, url in ((client.post, "/api/me/characters"), (client.put, f"/api/me/characters/{char_id}")):
            response = method(url, json=char_data, headers={"Authorization": "Bearer " + make_login_key(A)})
            assert response.status_code == 200 and response.json()["display_name"] == real(A), response.text
        user_settings.update_settings(A, {"privacy": {"char_public": False}})
        assert client.get(f"/api/characters/{A}/{char_id}", headers={"Authorization": "Bearer " + make_login_key(B)}).status_code == 403
        assert get(f"/api/characters/{A}/{char_id}")["display_name"] == real(A)

        # 第三等奖只有 stats 含身份；头条重建不改任意用户正文。
        third = deepcopy(report)
        third["lottery"]["immortal"]["winners"] = [
            {"user_id": int(A), "name": "旧昵称" + A, "digits": "1200", "tier": "三等奖(2A)"}]
        third["headline"] = {"kind": "immortal_jackpot", "title": "仙人彩开奖",
                             "body": "本期开奖号码 1234，无人命中大奖，1 注命中三等奖，奖池滚存。",
                             "stats": [{"label": "开奖号码", "value": "1234"},
                                       {"label": "中奖注数", "value": 1},
                                       {"label": "中奖名单", "value": "旧昵称111111（1200）"},
                                       {"label": "总奖池", "value": 99}]}
        third_original = deepcopy(third)
        shown = _display_report(third, B)
        assert shown["headline"]["body"] == third["headline"]["body"]
        assert shown["headline"]["stats"][2]["value"] == ANON + "（1200）"
        assert third == third_original
        assert _display_report(third, A) == third
        empty = deepcopy(report)
        empty["lottery"]["immortal"]["winners"] = []
        empty["headline"] = {"kind": "immortal_jackpot", "title": "仙人彩奖池滚存", "body": "无人中奖，奖池滚存。", "stats": []}
        assert _display_report(empty, B)["headline"] == empty["headline"]
        plain = deepcopy(report)
        plain["headline"] = {"kind": "activity", "title": "旧昵称111111 的活动", "body": "用户正文旧昵称111111", "stats": []}
        assert _display_report(plain, B)["headline"] == plain["headline"]

        # 缺身份来源只降级头条，其他内容可读，响应与存储互不污染。
        broken_reports = []
        for field in ("digits", "pool", "winners"):
            broken = deepcopy(report)
            del broken["lottery"]["immortal"][field]
            broken_reports.append(broken)
        broken = deepcopy(report)
        broken["lottery"]["immortal"] = None
        broken_reports.append(broken)
        for field in ("user_id", "name", "digits", "tier"):
            broken = deepcopy(report)
            del broken["lottery"]["immortal"]["winners"][0][field]
            broken_reports.append(broken)
        broken = deepcopy(report)
        broken["lottery"] = None
        broken_reports.append(broken)
        for bad_id in ("invalid", None, -1):
            broken = deepcopy(report)
            broken["lottery"]["immortal"]["winners"][0]["user_id"] = bad_id
            broken_reports.append(broken)
        for index, broken in enumerate(broken_reports):
            key = "legacy-" + str(index)
            original = deepcopy(broken)
            db.weekly.upsert(key, int(GROUP_ID), broken)
            for viewer in (A, B):
                shown = get("/api/weekly/" + key, viewer)
                assert shown["headline"] == {"kind": "immortal_jackpot", "title": "仙人彩历史头条",
                                             "body": "历史头条缺少身份资料，暂不展示详情。", "stats": []}
                assert shown["voices"]["quotes"][0]["text"] == "旧昵称111111 是用户原文"
                assert shown["checkin"]["full_week"][0]["name"] == ("旧昵称" + A if viewer == A else ANON)
                source = (broken["lottery"] or {}).get("immortal")
                if source and source.get("winners"):
                    winner = source["winners"][0]
                    if not str(winner.get("user_id", "")).isdigit():
                        assert shown["lottery"]["immortal"]["winners"][0]["name"] == "身份资料缺失"
            assert _display_report(broken, B)["headline"]["title"] == "仙人彩历史头条"
            assert broken == original == db.weekly.get(key, int(GROUP_ID))["data_json"]
        listing = get("/api/weekly", B)["items"]
        assert all(r["headline_title"] == "仙人彩历史头条" for r in listing if r["week_key"].startswith("legacy-"))
        user_settings.update_settings(A, {"privacy": {"identity_public": True, "char_public": True}})
        check_surfaces(B, False)
        print("ok - 周报三种头条、损坏旧资料局部降级、原始数据保留、TRPG权限及全部调用方")

print("identity privacy checks passed")
