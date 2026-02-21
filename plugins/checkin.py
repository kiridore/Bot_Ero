import re
from core.base import Plugin
from core.cq import text,at
from core.logger import logger
from core.utils import add_user_point, get_monday_to_monday

# 打卡插件
class CheckinPlugin(Plugin):
    def match(self):
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
            self.dbmanager.insert_checkin(self.context["user_id"], img_list)
            checkin_list = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], start_date, end_date)
            if is_first:
                add_user_point(self.dbmanager, self.context['user_id'], 1)
                self.api.send_msg(at(self.context["user_id"]), text("\n🌟打卡成功喵🌟\n收录了{}张图片\n完成本周首次打卡喵，拿好你的点数~".format(len(img_list))))
            else:
                self.send_msg(at(self.context["user_id"]), text("\n⭐打卡成功喵⭐\n收录了{}张图片\n这周已经提交了{}张图了喵".format(len(img_list), len(checkin_list))))
