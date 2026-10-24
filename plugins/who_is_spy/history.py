"""新历史生命周期；不读取旧JSON，也不恢复内存房间。"""
import time

from core.database_manager import DbManager
from core.logger import logger


def recover_interrupted_games():
    """仅在bot启动接收事件前调用一次，不能放在重连循环或DbManager构造中。"""
    db = DbManager()
    try:
        with db.who_is_spy.transaction():
            count = db.who_is_spy.interrupt_open(time.time())
    finally:
        db.conn.close()
    if count:
        logger.info('已将 %s 条未结束卧底记录标记为重启中断，不恢复对局或补发奖励', count)
    return count
