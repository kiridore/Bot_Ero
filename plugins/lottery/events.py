"""逐次结算→通知周常/称号→整理结果→下一次；一键抽奖仍在同一事件线程。"""
from core.cq import at, text
from core.database_manager import DbManager
from core.plugin_dispatch import subscribe
from core.logger import logger
from plugins.lottery.engine import perform_draw, FREE_DRAW_HINT
from plugins.title import get_title_def


def finish_bulk(operation, payload, done):
    operation.output.submit(f"🎲 一键抽奖完成：共 {done} 次", kind="forward_text",
                            merge=payload["command_key"], node=0, order=0)


@subscribe("lottery.draw.requested", "lottery")
def draw_requested(operation, payload):
    # 由命令入口和事件消费者共同保证不能绕过称号依赖。
    if not operation.is_enabled("title"):
        operation.output.submit("称号功能已关闭，暂时无法抽奖。请联系超级用户开启称号功能。")
        return
    db = DbManager()
    try:
        outcome = perform_draw(db, payload, operation.is_enabled("redeem_shop"))
    except Exception:
        logger.exception("抽奖结算失败，操作=%s 来源=%s", operation.id, payload["source_operation"])
        operation.failures.append("lottery")
        operation.output.failure("lottery")
        if payload["bulk"]:
            finish_bulk(operation, payload, payload["index"] - 1)
        return
    finally:
        db.conn.close()
    if outcome["status"] == "ok":
        operation.publish("lottery.draw.completed", dict(payload, outcome=outcome))
        return
    if outcome["status"] == "duplicate":
        operation.output.submit("这次抽奖已处理，请勿重复提交。")
        if payload["bulk"] and payload["index"] > 1:
            finish_bulk(operation, payload, payload["index"] - 1)
        return
    if outcome["status"] == "limit":
        hint = "你今天已打卡，可抽5次" if outcome["checked_in"] else "今日未打卡，默认可抽2次"
        message = f"今天抽卡次数已用完（{outcome['count']}/{outcome['limit']}）。{hint}。"
        if payload["index"] == 1:
            operation.output.submit([at(payload["user_id"]), text(message)], kind="segments")
            return
    elif payload["bulk"]:
        message = "积分不足，停止抽奖（已完成 {} 次，剩余 {} 次未抽）。当前积分：{}".format(
            payload["index"] - 1, payload["remaining"] - payload["index"] + 1, outcome["points"],
        )
    else:
        message = f"抽奖需要1点积分，你现在只有{outcome['points']}点喵"
    if payload["bulk"]:
        operation.output.submit(message, **payload["output"], order=20)
        finish_bulk(operation, payload, payload["index"] - 1)
    else:
        operation.output.submit([at(payload["user_id"]), text(message)], kind="segments")


def result_text(outcome, points):
    result = outcome["result"]
    free, exempt, cost = outcome["free"], outcome["exempt"], outcome["cost"]
    hint = FREE_DRAW_HINT if free else "抽奖增强：本次不消耗积分" if exempt else "本次消耗：1积分"
    mid = hint + "\n" if free or exempt else ""
    if result["type"] == "points":
        reward = result["value"]
        head = "*摇骰子* 居然什么都没有抽到呢……" if reward == 0 else f"*摇骰子* 居然抽到了……{reward}点积分！"
        return f"{head}\n本次净变化：{reward - cost}积分\n{mid}当前积分：{points}"
    if result["type"] in ("title_new", "title_duplicate"):
        tid = result["value"]
        title = get_title_def(tid) or {"name": "未知称号", "rarity": "unknown"}
        title_text = f"[{tid}] 「{title['name']}」 ({title['rarity']})"
        if result["type"] == "title_new":
            return f"*摇骰子* 居然抽到了……解锁称号 {title_text}！\n{hint}\n当前积分：{points}"
        return f"*摇骰子* 居然抽到了……已拥有称号 {title_text}！\n已返还{result.get('rebate', 0)}积分。\n{mid}当前积分：{points}"
    if result["type"] == "title_none":
        return f"*摇骰子* 居然抽到了……{result['rarity']}称号位！\n当前没有可抽取的该稀有度称号。\n{mid}当前积分：{points}"
    return f"*摇骰子* 居然抽到了……{result['value']}！\n{hint}\n当前积分：{points}"


@subscribe("lottery.draw.completed", "lottery", order=30)
def report_draw(operation, payload):
    db = DbManager()
    try:
        row = db.conn.execute("SELECT points FROM user_assets WHERE user_id = ?", (str(payload["user_id"]),)).fetchone()
        message = result_text(payload["outcome"], row[0] if row else 0)
    finally:
        db.conn.close()
    if payload["bulk"]:
        operation.output.submit(message, **payload["output"], order=20)
    else:
        operation.output.submit([at(payload["user_id"]), text(message)], kind="segments", order=20)
    if payload["bulk"] and payload["index"] < payload["remaining"]:
        index = payload["index"] + 1
        next_payload = {key: value for key, value in payload.items() if key != "outcome"}
        next_payload.update(index=index, source_operation=f"{payload['command_key']}:{index}",
                            output=dict(payload["output"], node=index))
        operation.publish("lottery.draw.requested", next_payload)
    elif payload["bulk"]:
        finish_bulk(operation, payload, payload["index"])
