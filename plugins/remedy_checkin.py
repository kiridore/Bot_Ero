from datetime import datetime, timedelta
from core import utils
from core.base import Plugin
from core.cq import text
from core.utils import get_monday_to_monday

class RemedyCheckinPlugin(Plugin):
    super_mode = False
    
    def match(self, message_type):
        if self.on_command("/单日补卡"):
            return True
        elif self.on_command("/补卡"):
            return True
        elif self.on_command("/超级补卡") and self.admin_user():
            self.super_mode = True
            return True
        return False

    def handle(self):
        if self.args[0] == "/单日补卡":
            self.handle_single_day_remedy()
            return

        if len(self.args) > 1:
            try:
                dt = datetime.strptime(self.args[1], "%Y-%m-%d") + timedelta(hours=8)
            except Exception as e:
                self.api.send_msg(text("{}格式不正确".format(self.args[1])))
                return

            user_id = self.context['user_id']
            if len(self.args) > 2:
                user_id = self.args[2] # 特殊补卡指令可以给其他人补卡

            start, end = get_monday_to_monday(dt)
            rows = self.dbmanager.search_target_user_checkin_range(user_id, start, end)

            cost = 4

            if len(rows) == 0:
                points = self.dbmanager.get_user_point(user_id)
                if points >= cost or self.super_mode:
                    success_msg = "{}-{}原来没有打卡吗？真拿你没办法……\n*涂写*好了帮你补上了喵，一共消费{}点数，谢谢惠顾喵"
                    self.api.send_msg(text(success_msg.format(start.split(" ")[0], end.split(" ")[0], cost)))
                    self.dbmanager.remedy_checkin(user_id, start.split(" ")[0])
                    if not self.super_mode:
                        utils.add_user_point(self.dbmanager, user_id, cost * -1)
                else:
                    self.api.send_msg(text("补卡当然不是免费的喵!\n你现在现在点数是：{}\n补卡需要{}点喵".format(points, cost)))
            else:
                self.api.send_msg(text("上当了喵！{}-{}你已经打过卡了喵！".format(start.split(" ")[0], end.split(" ")[0])))

        else:
            self.find_remedy()

    def handle_single_day_remedy(self):
        if len(self.args) <= 1:
            suggest_day = self.find_single_day_remedy()
            if suggest_day is None:
                self.api.send_msg(text("今年每天都打过卡了喵，不需要单日补卡"))
            else:
                self.api.send_msg(text("找到最近漏打卡日期：{}\n可使用指令：/单日补卡 {}".format(suggest_day, suggest_day)))
            return

        try:
            day = datetime.strptime(self.args[1], "%Y-%m-%d")
        except Exception:
            self.api.send_msg(text("{}格式不正确".format(self.args[1])))
            return

        day_start = day.strftime("%Y-%m-%d 08:00:00")
        day_end = (day + timedelta(days=1)).strftime("%Y-%m-%d 08:00:00")
        user_id = self.context["user_id"]

        rows = self.dbmanager.search_target_user_checkin_range(user_id, day_start, day_end)
        if len(rows) > 0:
            self.api.send_msg(text("{} 这一天你已经打过卡了喵".format(self.args[1])))
            return

        cost = 2
        points = self.dbmanager.get_user_point(user_id)
        if points < cost:
            self.api.send_msg(text("补卡当然不是免费的喵!\n你现在点数是：{}\n单日补卡需要{}点喵".format(points, cost)))
            return

        self.dbmanager.remedy_checkin_one_day(user_id, self.args[1])
        utils.add_user_point(self.dbmanager, user_id, cost * -1)
        self.api.send_msg(text("{} 已补卡成功喵，一共消费{}点数".format(self.args[1], cost)))

    def find_single_day_remedy(self):
        # 从昨天开始往前找，返回最近一次未打卡日期（按 8 点结算）
        date = datetime.today() - timedelta(days=1)
        current_year = date.year
        while date.year == current_year:
            day_start = date.strftime("%Y-%m-%d 08:00:00")
            day_end = (date + timedelta(days=1)).strftime("%Y-%m-%d 08:00:00")
            rows = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], day_start, day_end)
            if len(rows) == 0:
                return date.strftime("%Y-%m-%d")
            date = date - timedelta(days=1)
        return None

    def find_remedy(self):
        date = datetime.today()
        current_year = date.year

        while True:
            pre_date = date - timedelta(days=7)
            tmp_start, tmp_end = get_monday_to_monday(pre_date) # 这个函数里已经自带了8小时偏移，正常传入日期即可

            if datetime.strptime(tmp_end, "%Y-%m-%d %H:%M:%S").year != current_year:
                self.api.send_msg(text("{}每一周都打了卡呢！完全不需要补卡喵".format(current_year)))
                break

            rows = self.dbmanager.search_target_user_checkin_range(self.context['user_id'], tmp_start, tmp_end)
            if len(rows) == 0:
                self.api.send_msg(text("找到{}-{}这一周没有打卡喵，使用指令\"/补卡 {}\"确认补卡喵".format(tmp_start.split(" ")[0], tmp_end.split(" ")[0], tmp_start.split(" ")[0])))
                break

            date = pre_date

