from datetime import datetime, timedelta
from core.base import Plugin
from core.cq import text
from core.utils import get_monday_to_monday

class RemedyCheckinPlugin(Plugin):
    super_mode = False
    
    def match(self):
        if self.on_command("/补卡"):
            return True
        elif self.on_command("/超级补卡") and self.admin_user():
            self.super_mode = True
            return True
        return False

    def handle(self):
        raw_data = self.context["message"][0]
        if raw_data['type'] != 'text':
            return
        msg = raw_data['data']['text']
        args = msg.split(" ")

        if len(args) > 1:
            dt = datetime.strptime(args[0], "%Y-%m-%d")
            user_id = args[1] # 特殊补卡指令可以给其他人补卡
            start, end = get_monday_to_monday(dt)
            rows = self.dbmanager.search_target_user_checkin_range(self.context['user_id'], start, end)

            if len(rows) == 0:
                points = self.dbmanager.get_user_point(self.context['user_id'])
                if points >= 3:
                    success_msg = "{}-{}原来没有打卡吗？真拿你没办法……\n*涂写*好了帮你补上了喵，一共消费3积分，谢谢惠顾喵"
                    self.send_msg(text(success_msg.format(start, end)))
                else:
                    self.send_msg(text("补卡当然不是免费的喵！你现在只有{}是不会帮你补卡的喵".format(points)))
            else:
                self.send_msg(text("上当了喵！{}-{}你已经打过卡了喵！".format(start, end)))

        else:
            self.find_remedy()

    def find_remedy(self):
        date = datetime.today()

        while True:
            pre_date = date - timedelta(days=7)
            tmp_start, tmp_end = get_monday_to_monday(pre_date) # 这个函数里已经自带了8小时偏移，正常传入日期即可

            if pre_date.year != date.year:
                self.send_msg(text("{}每一周都打了卡呢！完全不需要补卡喵".format(date.year)))
                break

            rows = self.dbmanager.search_target_user_checkin_range(self.context['user_id'], tmp_start, tmp_end)
            if len(rows) == 0:
                self.send_msg(text("找到{}-{}这一周没有打卡喵，使用指令\"/补卡 {}\"确认补卡喵".format(tmp_start, tmp_end, tmp_start)))
                break

            date = pre_date

