"""个人偏好 API 与登录内图案头像；独立进程、全部数据路径隔离。"""

import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _env import write_config

_tmp = tempfile.TemporaryDirectory(prefix="botero_settings_preferences_")
os.environ["BOTERO_CONFIG"] = write_config(_tmp.name)

from fastapi.testclient import TestClient
from PIL import Image
from core import user_settings
from core.auth import make_login_key
from core.gen_image.identicon import generate_identicon
from webapp.app import app

UID = "123456"
headers = {"Authorization": "Bearer " + make_login_key(int(UID))}
keys = (("privacy", "identity_public"), ("timeline", "show_others_checkin"), ("watermark", "enabled"))

with TestClient(app) as client:
    assert client.get("/api/me/settings").status_code == 401
    assert client.put("/api/me/settings", json={}).status_code == 401
    assert client.get("/identicon/123456.png", follow_redirects=False).status_code == 401
    initial = client.get("/api/me/settings", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["privacy"] == {}
    assert initial.json()["timeline"] == {"show_others_checkin": True}
    assert initial.json()["watermark"] == {"enabled": True}
    assert user_settings.get_settings(UID) == {}

    # 空的嵌套更新不能把模型默认值写入文件。
    result = client.put("/api/me/settings", headers=headers, json={"timeline": {}, "watermark": {}})
    assert result.status_code == 200, result.text
    raw = user_settings.get_settings(UID)
    assert "show_others_checkin" not in raw.get("timeline", {})
    assert "enabled" not in raw.get("watermark", {})

    user_settings.update_settings(UID, {
        "email": "bound@example.test", "email_bound_at": "2026-01-01",
        "privacy": {"char_public": False, "checkin_display_private": "text", "checkin_display_group": "blur"},
    })
    for group, key in keys:
        result = client.put("/api/me/settings", headers=headers, json={group: {key: False}})
        assert result.status_code == 200, result.text
        assert result.json()[group][key] is False
        assert result.json() == client.get("/api/me/settings", headers=headers).json()
    saved = user_settings.get_settings(UID)
    for group, key in keys:
        assert saved[group][key] is False
        for bad in ("false", "true", 0, 1, 0.0, None, [], {}):
            result = client.put("/api/me/settings", headers=headers, json={group: {key: bad}})
            assert result.status_code == 422, (group, bad, result.text)
            assert user_settings.get_settings(UID) == saved
    result = client.put("/api/me/settings", headers=headers, json={
        "email": "attacker@example.test", "email_bound_at": "changed",
        "privacy": {"checkin_display_group": "hidden"},
    })
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["email"] == "bound@example.test" and data["email_bound_at"] == "2026-01-01"
    assert data["privacy"]["char_public"] is False
    assert data["privacy"]["checkin_display_private"] == "text"
    assert data["privacy"]["checkin_display_group"] == "hidden"
    for group, key in keys:
        assert data[group][key] is False
    for group, key in keys:
        result = client.put("/api/me/settings", headers=headers, json={group: {key: True}})
        assert result.status_code == 200 and result.json()[group][key] is True
    # 旧 privacy 字段不收紧校验。
    result = client.put("/api/me/settings", headers=headers, json={"privacy": {"char_public": "legacy"}})
    assert result.status_code == 200 and result.json()["privacy"]["char_public"] == "legacy"
    assert (user_settings.SETTINGS_ROOT / UID).is_file()
    assert not (user_settings.SETTINGS_ROOT / (UID + ".json")).exists()
    other_headers = {"Authorization": "Bearer " + make_login_key(654321)}
    assert client.get("/api/me/settings", headers=other_headers).json()["privacy"] == {}

    image = client.get("/identicon/123456.png", headers=headers)
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "private, max-age=86400"
    with Image.open(BytesIO(image.content)) as decoded:
        assert decoded.size == (128, 128)
        assert decoded.tobytes() == generate_identicon(UID).tobytes()
    assert image.content == client.get("/identicon/00123456.png", headers=headers).content
    assert image.content != client.get("/identicon/654321.png", headers=headers).content
    for invalid in ("abc", "-123", "1.5", "１２３"):
        assert client.get(f"/identicon/{invalid}.png", headers=headers).status_code == 422
    client.cookies.set("botero_key", make_login_key(654321))
    assert client.get("/identicon/123456.png").content == image.content

print("ok - settings strict booleans, partial updates, email protection, persistence, authenticated identicon")
_tmp.cleanup()
