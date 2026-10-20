# 本轮事件与接口核查

核查来源为specs/llms.txt所列LLOneBot单页，另以OneBot11标准补充接口字段：

- 好友请求 https://api.luckylillia.com/schema-189483968.md ：post_type=request、request_type=friend、user_id、flag。
- 好友添加 https://api.luckylillia.com/schema-189483970.md ：notice_type=friend_add、user_id。
- 好友处理 https://api.luckylillia.com/api-149701143.md ：flag、approve、remark；拒绝传false，remark空。
- 群邀请 https://api.luckylillia.com/schema-189483969.md ：request_type=group、sub_type=invite、group_id、user_id、flag。user_id定义为invite类型邀请者，不用可缺省为0的invitor_id替代。
- 群处理 https://api.luckylillia.com/api-149642556.md ；标准 https://github.com/botuniverse/onebot-11/blob/master/api/public.md 明确sub_type须与上报对应，拒绝传invite及approve=false，不公开内部封禁原因。
- 群增减 https://api.luckylillia.com/schema-189483976.md 、https://api.luckylillia.com/schema-189483975.md ：user_id是变化的成员，self_id是机器人；只在两者一致时执行自身生命周期事实维护，operator_id不能当作离群者。
- 群撤回 https://api.luckylillia.com/schema-189483978.md ：user_id是原消息发送者，operator_id是撤回操作者，message_id标识被撤回消息。

返回结果仅status=ok且整数retcode=0确认成功；failed且非零整数确认失败，缺失/异常/超时均未知。既有group_review.response_result保留导入兼容，实际实现移到core.blacklist供两处复用。

群拒绝先原子预留申请，再调用接口并保存结果；重复事件不重发已尝试的拒绝（包括明确失败）。好友拒绝一次事件只尝试一次，不自动重试；未新增好友请求永久去重表或重试队列。
