import time

from datetime import datetime
from core import ws_controller
from core.logger import logger
from plugins import *
import core.context as context

if __name__ == "__main__":
    ws_controller.init()
    while True:  # 掉线重连
        # 数据储存
        logger.info("数据库启动")
        context.script_start_time = datetime.now()
        ws_controller.WS_APP.run_forever()

        if context.should_shutdown:
            break

        time.sleep(5)

