"""测试用 config.yaml 生成器：conftest 与 check_*.py 共用。

返回写入的配置文件路径。section_overrides 按节深合并覆盖默认值，例如：
    write_config(_tmp, paths={"db": _db}, timeline={"token": "test-timeline-token"})
"""


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def write_config(tmp_dir: str, **section_overrides) -> str:
    import os

    cfg = {
        "bot": {
            "qq": "3915014383", "nickname": "测试bot", "super_users": [1057613133],
            "default_group": 296470819, "ws_url": "ws://127.0.0.1:3001", "ws_token": "123456",
            "download_proxy": "",
            "llonebot_data_path": os.path.join(tmp_dir, "onebot_data"),
            "python_data_path": os.path.join(tmp_dir, "server_data"),
            "onebot_qq_volume": "",
        },
        # OneBot HTTP 指向必然拒绝连接的地址：昵称/头像解析立即失败降级
        "onebot": {"http_url": "http://127.0.0.1:1", "token": "123456"},
        "paths": {
            "db": os.path.join(tmp_dir, "data.db"),
            "message_log_db": os.path.join(tmp_dir, "message_log.db"),
            "images": os.path.join(tmp_dir, "record_images"),
            "trpg_chars": os.path.join(tmp_dir, "trpg_chars"),
            "user_settings": os.path.join(tmp_dir, "user_settings"),
            "activity": os.path.join(tmp_dir, "activity_archive"),
            "forum_images": os.path.join(tmp_dir, "forum_images"),
        },
        "thumbs": {"cache_dir": os.path.join(tmp_dir, "thumb_cache")},
        "auth": {"salt": "test-salt", "old_salts": []},
        "timeline": {"url": "http://127.0.0.1:8765", "token": "test-timeline-token"},
    }
    cfg = _merge(cfg, section_overrides)
    for sub in ("record_images", "trpg_chars", "user_settings", "activity_archive",
                "forum_images", "thumb_cache", "onebot_data", "server_data"):
        os.makedirs(os.path.join(tmp_dir, sub), exist_ok=True)
    path = os.path.join(tmp_dir, "config.yaml")
    with open(path, "w", encoding="utf-8") as f:
        import yaml
        yaml.safe_dump(cfg, f, allow_unicode=True)
    return path
