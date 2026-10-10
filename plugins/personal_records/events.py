"""注册完成通知：personal_records 对外开放时为新账号发送资料卡（新用户全零卡）。"""
import os

from core.cq import at, image
from core.database_manager import DbManager
from core.plugin_dispatch import subscribe
from core import context as runtime_context
from core import utils
from core.logger import logger


def _render_card(db, uid) -> str | None:
    """复用 /档案 渲染管线；头像获取失败走既有无头像降级。返回图片绝对路径。"""
    from core.gen_image import PersonalRecordStats, gen_personal_record_card
    from plugins.personal_records import _load_avatar_from_url
    from datetime import datetime
    rows = db.checkin.search_year(uid, datetime.today().year)
    time_map = {}
    day_count = [0] * 366
    for row in rows:
        if row[3] != "remedy_checkin":
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
            day_count[utils.day_of_year(row[2]) - 1] += 1
        else:
            day_count[utils.day_of_year(row[2]) - 1] = -1
    streaks = db.checkin.streaks(uid)
    stats = PersonalRecordStats(
        year=datetime.today().year,
        total_distinct_days=len(time_map),
        total_checkin_images=len(rows),
        current_weekly=streaks["current_weekly"],
        longest_weekly=streaks["longest_weekly"],
        current_daily=streaks["current_daily"],
        longest_daily=streaks["longest_daily"],
        points=db.points.get(uid),
    )
    avatar = None
    try:
        from core.api import ApiWrapper
        api = ApiWrapper({"user_id": uid, "post_type": "message", "message_type": "private",
                          "message": [], "time": 0})
        url = api.get_qq_avatar(uid)
        if url:
            avatar = _load_avatar_from_url(url)
    except Exception:
        logger.warning("注册资料卡头像获取失败，按无头像渲染（用户 %s）", uid, exc_info=True)
    gen_personal_record_card(
        stats.year, day_count, uid, stats,
        user_display_name=str(uid), avatar=avatar,
    )
    return os.path.abspath("{}/personal_records/{}_calendar_heatmap_monthly.png".format(
        runtime_context.llonebot_data_path, uid))


@subscribe("register.completed", "show_personal_records", order=60)
def send_registration_card(operation, payload):
    if not runtime_context.effective_for_scope("show_personal_records",
                                               user_id=payload["user_id"]):
        return  # 插件未对该账号开放：静默跳过（spec 契约）
    db = DbManager()
    try:
        path = _render_card(db, payload["user_id"])
    except Exception:
        logger.exception("注册资料卡生成失败（用户 %s），跳过发卡", payload["user_id"])
        return
    finally:
        db.conn.close()
    if path and os.path.isfile(path):
        operation.output.submit([at(payload["user_id"]), image("file://" + path)],
                                kind="segments", target=("private", payload["user_id"]))
