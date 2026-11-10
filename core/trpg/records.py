"""跑团记录目录：路径解析、合法性校验与结构化数据读写。

bot 进程是唯一写入方（append_message / rewrite_meta），webapp 只读
（read_meta / iter_messages）；路径根按 config.PYTHON_DATA_PATH 解析，
非法群号、目录名与媒体文件名一律抛 ValueError，不拼进文件系统路径。
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from core import config as _config

START_DIR_FORMAT = "%Y-%m-%d_%H-%M-%S"

_GROUP_ID_RE = re.compile(r"^\d+$")
_START_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")
_MEDIA_NAME_RE = re.compile(r"^img_\d{4}\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE)

# messages.jsonl 每行必含字段（缺字段视为坏行）
MESSAGE_KEYS = ("time", "sender_type", "user_id", "nickname", "char_name", "role", "segments")


def start_dir_name(dt: datetime) -> str:
    return dt.strftime(START_DIR_FORMAT)


def records_root() -> Path:
    return Path(_config.PYTHON_DATA_PATH) / "trpg_records"


def group_dir(group_id) -> Path:
    text = str(group_id)
    if not _GROUP_ID_RE.match(text):
        raise ValueError(f"非法群号：{group_id!r}")
    return records_root() / text


def record_dir(group_id, start_dir) -> Path:
    text = str(start_dir)
    if not _START_DIR_RE.match(text):
        raise ValueError(f"非法记录目录名：{start_dir!r}")
    return group_dir(group_id) / text


def media_file(group_id, start_dir, name) -> Path:
    text = str(name)
    if not _MEDIA_NAME_RE.match(text):
        raise ValueError(f"非法媒体文件名：{name!r}")
    return record_dir(group_id, start_dir) / "imgs" / text


def ensure_record_dir(group_id, start_dir) -> Path:
    path = record_dir(group_id, start_dir)
    (path / "imgs").mkdir(parents=True, exist_ok=True)
    return path


def append_message(record_path, entry: dict) -> None:
    with open(Path(record_path) / "messages.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()


def rewrite_meta(record_path, meta: dict) -> None:
    path = Path(record_path) / "meta.json"
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_meta(record_path) -> dict | None:
    try:
        with open(Path(record_path) / "meta.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def iter_messages(record_path) -> tuple[list[dict], int]:
    """读取 messages.jsonl，返回 (有效消息, 跳过行数)；坏行与缺字段行跳过。"""
    entries: list[dict] = []
    skipped = 0
    try:
        handle = open(Path(record_path) / "messages.jsonl", "r", encoding="utf-8")
    except OSError:
        return entries, skipped
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if (
                not isinstance(entry, dict)
                or any(key not in entry for key in MESSAGE_KEYS)
                or not isinstance(entry["segments"], list)
            ):
                skipped += 1
                continue
            entries.append(entry)
    return entries, skipped
