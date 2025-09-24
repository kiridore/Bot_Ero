import time

from datetime import datetime
from core import ws_controller
from core.logger import logger
import core.context as context

if __name__ == "__main__":
    ws_controller.init()
    while True:  # 掉线重连
        context.script_start_time = datetime.now()
        ws_controller.WS_APP.run_forever()

        if context.should_shutdown:
            break

        time.sleep(5)

