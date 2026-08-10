"""兑换码注册表：新增兑换码 = 在此文件加一个 REDEEM_CODES 条目 + 一个回调函数。

回调契约: callback(dbmanager, user_id, api) -> str | None
返回值非空时拼在"兑换成功"回复末尾，用于描述发放的奖励。
积分: from core.utils import add_user_point; add_user_point(db, user_id, n)
称号: db.titles.unlock(user_id, title_id)
"""
import re
from typing import Optional

from core.api import ApiWrapper
from core.database_manager import DbManager
from core.utils import add_user_point

CODE_PATTERN = re.compile(r"^[A-Z]{4}-[A-Z]{4}-[A-Z]{4}$")

TESTER_TITLE_ID = 501
FIRST_ANNIVERSARY_TITLE_ID = 502
ANNIVERSARY_POINTS = 10


def _grant_tester_title(db: DbManager, user_id: int, api: ApiWrapper) -> Optional[str]:
    """首个兑换码回调：解锁「测试员」称号。"""
    db.titles.unlock(user_id, TESTER_TITLE_ID)
    return "解锁称号：「测试员」"


def _grant_first_anniversary(db: DbManager, user_id: int, api: ApiWrapper) -> Optional[str]:
    """一周年兑换码回调：解锁「1st」称号 + 10 积分。"""
    db.titles.unlock(user_id, FIRST_ANNIVERSARY_TITLE_ID)
    add_user_point(db, user_id, ANNIVERSARY_POINTS)
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
