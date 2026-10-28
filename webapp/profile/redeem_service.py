"""网页端兑换码服务（注册表 + 单事务占位/发奖）。不导入 plugins 包。

兑换码维护方式与旧 QQ 插件等价：在此文件加 REDEEM_CODES 条目 + 回调，重启 webapp 生效。
回调契约: callback(db: DbManager, user_id) -> str | None
返回值非空时作为奖励说明拼进成功消息与历史列表。
称号: db.titles.unlock(user_id, title_id, commit=False)
积分: db.points.adjust(user_id, n, commit=False)
回调必须使用 commit=False 写入，保证与占位同事务回滚。
"""
import re

from core.database_manager import DbManager

CODE_PATTERN = re.compile(r"^[A-Z]{4}-[A-Z]{4}-[A-Z]{4}$")

TESTER_TITLE_ID = 501
FIRST_ANNIVERSARY_TITLE_ID = 502
ANNIVERSARY_POINTS = 10


def _grant_tester_title(db: DbManager, user_id) -> str:
    db.titles.unlock(user_id, TESTER_TITLE_ID, commit=False)
    return "解锁称号：「测试员」"


def _grant_first_anniversary(db: DbManager, user_id) -> str:
    db.titles.unlock(user_id, FIRST_ANNIVERSARY_TITLE_ID, commit=False)
    db.points.adjust(user_id, ANNIVERSARY_POINTS, commit=False)
    return "解锁称号：「1st」，积分 +10"


REDEEM_CODES = {
    "TEST-CODE-TEST": {
        "description": "解锁「测试员」称号",
        "callback": _grant_tester_title,
    },
    "ONLY-YEAR-ONCE": {
        "description": "一周年专属：解锁「1st」称号 + 10 积分",
        "callback": _grant_first_anniversary,
    },
}

RETIRED_DESCRIPTION = "（已下架）"


def redeem_history(user_id) -> dict:
    """本人兑换历史：迁移前旧记录原样可见；已下架码只显示占位说明。"""
    db = DbManager()
    try:
        rows = db.redeem.history(user_id)
    finally:
        db.conn.close()
    return {
        "items": [
            {
                "code": code,
                "used_at": used_at,
                "description": REDEEM_CODES[code]["description"] if code in REDEEM_CODES else RETIRED_DESCRIPTION,
            }
            for code, used_at in rows
        ]
    }


def redeem_code(user_id, raw_code) -> dict:
    code = str(raw_code or "").strip().upper()  # 输入大小写不敏感，存储统一大写
    if not CODE_PATTERN.match(code):
        raise ValueError("兑换码格式不正确，应为 XXXX-XXXX-XXXX（大写字母）")
    entry = REDEEM_CODES.get(code)
    if entry is None:
        raise ValueError("兑换码不存在或已失效")

    db = DbManager()
    try:
        db.conn.execute("BEGIN IMMEDIATE")
        if not db.redeem.claim_in_transaction(user_id, code):
            db.conn.rollback()
            raise ValueError("你已使用过该兑换码")
        try:
            reward = entry["callback"](db, user_id)
        except Exception:
            db.conn.rollback()
            raise RuntimeError("兑换处理失败，请稍后再试")
        db.conn.commit()
    finally:
        db.conn.close()
    return {"success": True, "message": "兑换成功" + (f"，{reward}" if reward else "")}
