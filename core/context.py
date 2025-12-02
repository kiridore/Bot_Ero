# 一些全局运行时数据
from datetime import datetime

script_start_time = datetime.now()
should_shutdown = False
llonebot_data_path = "/app/llonebot/server_data"    # 使用api是用这个地址
python_data_path = "./server_data"                  # 在python脚本中访问用这个地址
onebot_qq_volume = "/var/lib/docker/volumes/onebot_qq_volume/_data"
