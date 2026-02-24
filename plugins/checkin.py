from core.base import Plugin
from core.cq import text,at
from core.logger import logger
from core.utils import add_user_point, get_monday_to_monday

# 打卡插件
class CheckinPlugin(Plugin):
    def match(self, message_type):
        return self.on_begin_with("/打卡")

    def handle(self):
        img_list = []
        for message_unit in self.context["message"]:
            if message_unit['type'] == 'image':
                img_list.append(message_unit['data']['file'])
        if len(img_list) <= 0:
            self.api.send_msg(text("没有图片是没办法打卡的喵"))
        else:
            for img_name in img_list :
                # 找到的图片列表
                logger.debug("{}".format(self.api.get_image(img_name)))

            start_date, end_date = get_monday_to_monday()

            # 确定是否首次打卡
            before_checkin_list = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], start_date, end_date)
            is_first = False
            if len(before_checkin_list) == 0:
                is_first = True

            #先打卡后搜索
            streak_res = self.dbmanager.get_user_streaks(self.context["user_id"])
            self.dbmanager.insert_checkin(self.context["user_id"], img_list)
            checkin_list = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], start_date, end_date)

            display_str = "\n🌟打卡成功喵🌟\n收录了{}张图片\n".format(len(img_list))

            if is_first:
                add_user_point(self.dbmanager, self.context['user_id'], 1)
                display_str += "完成本周首次打卡喵，拿好你的点数~"
            else:
                display_str += "这周已经提交了{}张图了喵".format(len(checkin_list))

            if streak_res["current_weekly"] > 1:
                display_str += "\n已经连续打卡了{}周了，真厉害喵！".format(streak_res["current_weekly"])

            self.api.send_msg(at(self.context["user_id"]), text(display_str))
