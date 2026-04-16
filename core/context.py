# 一些全局运行时数据
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.base import Plugin

script_start_time = datetime.now()
llonebot_data_path = "/app/llonebot/server_data"    # 使用api是用这个地址
python_data_path = "./server_data"                  # 在python脚本中访问用这个地址
onebot_qq_volume = "/var/lib/docker/volumes/onebot_qq_volume/_data"
startup_changelog_sent = False
recent_chat_records = []
plugin_registry: list[type["Plugin"]] = []
