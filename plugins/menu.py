from core import context
from core.api_wrapper import send_msg
from core.base import Plugin
from core.cq import text

class MenuPlugin(Plugin):
    commands = ["菜单", "帮助", "help"]
    desc = "查看所有支持功能~\n 指令\"/菜单 [指令名]\"可以查看详细帮助"
    short_desc = "查看所有支持功能~"
    only_admin = False

    def handle(self):
        if len(self.args) == 0:
        #根据每个类型的short_desc自动生成帮助
            list_desc = "小埃同学目前支持的功能有:\n"
            for P in Plugin.__subclasses__():
                commands_list = ""
                for command in P.commands:
                    commands_list += "{}{} ".format(context.command_prefix, command)
                if len(commands_list) > 0:
                    list_desc += "{} - {}\n".format(commands_list, P.short_desc)
            send_msg(self.message_type, self.target_id, text(list_desc))

#             send_msg(self.message_type, self.target_id, text("""小埃同学现在还只有打卡功能喵
# ---------------------------
# /打卡 加上你的图就可以完成打卡了喵
# /本周打卡图 统计本周上传的打卡图，通过小窗发送
# /个人打卡记录 /档案 统计有史以来所有的打卡次数、打卡日历图
# /撤回打卡 撤回本周最近一次打卡
# -----仅群聊可用------------
# /本周板油 统计本周有那些板油完成了打卡"""))
        else:
            bind_plugin = context.command_bind.get(self.args[0])
            if bind_plugin == None:
                send_msg(self.message_type, self.target_id, text("找不到 /{} 指令的介绍喵".format(self.args[0])))
            else:
                send_msg(self.message_type, self.target_id, text("{}".format(bind_plugin.desc)))
