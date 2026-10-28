"""可传播 bot 图片的身份/水印入口回归；网络、发送与数据目录全部隔离。"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from core import context, gen_image, user_settings
from core.api import ApiWrapper
from core.event import Event
from core.gen_image.identicon import generate_identicon
from core.message_output import MessageOutput
from plugins import personal_records, leaderboard, week_list
from plugins.personal_records import events

UID = 424242
OTHER = 777001
GROUP = 123456


@pytest.fixture(autouse=True)
def isolated_images(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "SETTINGS_ROOT", tmp_path / "settings")
    monkeypatch.setattr(context, "python_data_path", str(tmp_path))
    monkeypatch.setattr(context, "llonebot_data_path", str(tmp_path))
    monkeypatch.setattr(context, "TITLE_PREFIX_PROVIDER", None)
    monkeypatch.setattr("requests.get", Mock(side_effect=AssertionError("禁止网络请求")))
    monkeypatch.setattr(ApiWrapper, "call_api", Mock(side_effect=AssertionError("禁止真实发送")))


def fake_db():
    db = Mock()
    db.checkin.search_year.return_value = []
    db.checkin.streaks.return_value = dict(current_weekly=0, longest_weekly=0,
                                         current_daily=0, longest_daily=0)
    db.points.get.return_value = 42
    db.titles.equipped_all.return_value = []
    return db


def command_plugin(cls, group_id=GROUP):
    raw = {"post_type": "message", "message_type": "group" if group_id else "private",
           "user_id": UID, "group_id": group_id, "message": [],
           "sender": {"card": "真实群名片", "nickname": "真实昵称"}}
    plugin = cls.__new__(cls)
    plugin.bot_event = Event(raw)
    plugin.dbmanager = fake_db()
    plugin.args = ["2024"]
    api = ApiWrapper.__new__(ApiWrapper)
    api.context = plugin.bot_event
    api.dbmanager = plugin.dbmanager
    api.call_api = Mock(return_value={"status": "ok", "data": {"message_id": 1}})
    api.get_qq_avatar = Mock(return_value="https://example.test/avatar")
    plugin.api = api
    return plugin


def set_preferences(public, enabled):
    if public is not None:
        user_settings.update_settings(UID, {"privacy": {"identity_public": public}})
    if enabled is not None:
        user_settings.update_settings(UID, {"watermark": {"enabled": enabled}})


def assert_record(render, public, enabled, expected_name, avatar):
    args, kwargs = render.call_args
    assert args[2] == UID
    assert kwargs["user_display_name"] == expected_name
    assert kwargs["watermark_text"] == (None if enabled is False else expected_name)
    expected_avatar = generate_identicon(UID) if public is False else avatar
    assert kwargs["avatar"].tobytes() == expected_avatar.tobytes()
    baseline = gen_image.build_personal_record_image(
        args[0], args[1], args[3], user_display_name=expected_name, avatar=expected_avatar)
    path = Path(context.python_data_path) / "personal_records" / f"{UID}_calendar_heatmap_monthly.png"
    with Image.open(path) as output:
        assert output.size == baseline.size
        assert (output.tobytes() == baseline.tobytes()) == (enabled is False)
    return path


@pytest.mark.parametrize("public", [None, True, False])
@pytest.mark.parametrize("enabled", [None, True, False])
@pytest.mark.parametrize("group_id", [None, GROUP])
def test_personal_records_watermark_text_and_real_target(monkeypatch, public, enabled, group_id):
    set_preferences(public, enabled)
    avatar = Image.new("RGB", (128, 128), "blue")
    load = Mock(return_value=avatar)
    monkeypatch.setattr(personal_records, "_load_avatar_from_url", load)
    render = Mock(wraps=gen_image.gen_personal_record_card)
    monkeypatch.setattr(personal_records, "gen_personal_record_card", render)
    plugin = command_plugin(personal_records.PersonalRecords, group_id)
    plugin.handle()
    name = user_settings.anonymous_name(UID) if public is False else "真实群名片"
    path = assert_record(render, public, enabled, name, avatar)
    assert plugin.api.get_qq_avatar.call_count == (0 if public is False else 1)
    assert load.call_count == (0 if public is False else 1)
    action, params = plugin.api.call_api.call_args.args
    assert action == ("send_group_msg" if group_id else "send_private_msg")
    assert params["group_id" if group_id else "user_id"] == (group_id or UID)
    assert params["message"][0]["data"]["qq"] == UID
    assert params["message"][1]["data"]["file"] == "file://" + str(path.resolve())


@pytest.mark.parametrize("public", [None, True, False])
@pytest.mark.parametrize("enabled", [None, True, False])
def test_registration_card_watermark_text_and_real_target(monkeypatch, public, enabled):
    set_preferences(public, enabled)
    avatar = Image.new("RGB", (128, 128), "blue")
    load = Mock(return_value=avatar)
    monkeypatch.setattr(personal_records, "_load_avatar_from_url", load)
    api = Mock()
    api.get_qq_avatar.return_value = "https://example.test/avatar"
    factory = Mock(return_value=api)
    monkeypatch.setattr("core.api.ApiWrapper", factory)
    render = Mock(wraps=gen_image.gen_personal_record_card)
    monkeypatch.setattr(gen_image, "gen_personal_record_card", render)
    monkeypatch.setattr(events, "DbManager", fake_db)
    monkeypatch.setattr(context, "effective_for_scope", Mock(return_value=True))
    send = Mock(return_value=1)
    output = MessageOutput(send, ("group", GROUP))
    events.send_registration_card(SimpleNamespace(output=output), {"user_id": UID})
    output.flush()
    name = user_settings.anonymous_name(UID) if public is False else str(UID)
    path = assert_record(render, public, enabled, name, avatar)
    assert factory.call_count == (0 if public is False else 1)
    assert load.call_count == (0 if public is False else 1)
    request = send.call_args.args[0]
    assert request.target == ("private", UID)
    assert request.content[0]["data"]["qq"] == UID
    assert request.content[1]["data"]["file"] == "file://" + str(path.resolve())


@pytest.mark.parametrize("module,cls", [(leaderboard, leaderboard.LeaderboardPlugin),
                                       (week_list, week_list.WeekListPlugin)])
def test_rank_identity_per_row_without_watermark_and_text_fallback(monkeypatch, module, cls):
    user_settings.update_settings(UID, {"privacy": {"identity_public": False}})
    plugin = command_plugin(cls)
    plugin.dbmanager.points.leaderboard.return_value = [(UID, 42), (OTHER, 10)]
    plugin.dbmanager.checkin.search_range.return_value = [
        (1, UID, "2024-01-02 09:00:00", "one.png"),
        (2, OTHER, "2024-01-03 09:00:00", "two.png")]
    plugin.api.get_group_member_info = Mock(side_effect=lambda uid: {"card": f"真实{uid}"})
    plugin._format_title_prefix = lambda uid: "「称号」"
    avatar = Image.new("RGB", (128, 128), "blue")
    fetch = Mock(return_value=avatar)
    monkeypatch.setattr(module, "fetch_avatar_cached", fetch)
    render = Mock(wraps=gen_image.render_rank_card)
    monkeypatch.setattr(module, "render_rank_card", render)
    save = Mock(wraps=gen_image.save_rank_png)
    monkeypatch.setattr(module, "save_rank_png", save)
    watermark = Mock(side_effect=AssertionError("多人图不得加水印"))
    monkeypatch.setattr(gen_image, "apply_watermark", watermark)
    monkeypatch.setattr("core.gen_image.watermark.apply_watermark", watermark)
    outputs = []
    for enabled in (True, False):
        for uid in (UID, OTHER):
            user_settings.update_settings(uid, {"watermark": {"enabled": enabled}})
        fetch.reset_mock()
        plugin.handle()
        fetch.assert_called_once_with(plugin.api, OTHER)
        rows = render.call_args.args[2]
        assert rows[0].name == user_settings.anonymous_name(UID)
        assert rows[0].avatar.tobytes() == generate_identicon(UID).tobytes()
        assert rows[1].name == f"「称号」真实{OTHER}"
        assert rows[1].avatar is avatar
        assert not render.call_args.kwargs
        outputs.append(save.call_args.args[1].tobytes())
    assert outputs[0] == outputs[1]
    watermark.assert_not_called()
    render.side_effect = RuntimeError("模拟图片生成失败")
    plugin.handle()
    action, params = plugin.api.call_api.call_args.args
    assert action == "send_group_msg" and params["group_id"] == GROUP
    body = params["message"][0]["data"]["text"]
    assert f"「称号」真实{UID}" in body
    assert f"「称号」真实{OTHER}" in body
    assert user_settings.anonymous_name(UID) not in body
