from core.base import Plugin
from core.cq import text

class MenuPlugin(Plugin):
    def match(self):
        return self.only_to_me() and self.on_full_match("菜单")

    def handle(self):
        self.send_msg(text("""
小埃同学现在还只有打卡功能喵
---------------------------
/打卡 加上你的图就可以完成打卡了喵
/本周打卡图 统计本周上传的打卡图，通过小窗发送
/个人打卡记录 统计有史以来所有的打卡次数
/本周板油 统计本周有那些板油完成了打卡
/撤回打卡 撤回本周最近一次打卡
            """))
