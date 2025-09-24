# 一些全局运行时数据
from datetime import datetime

NICKNAME = ["小埃同学", "bot"]         # 机器人昵称
SUPER_USER = [1057613133]   # 主人的 QQ 号
script_start_time = datetime.now()
should_shutdown = False

command_bind = {} # 动态生成的指令绑定表
command_prefix = "/"
