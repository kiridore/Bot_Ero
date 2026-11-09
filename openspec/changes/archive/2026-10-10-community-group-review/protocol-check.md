# 群审核协议核查

实施前在线读取以下权威单页（非仅根据本地索引猜测）：

- LLOneBot审批：https://api.luckylillia.com/api-149642556.md
- 邀请事件：https://api.luckylillia.com/schema-189483969.md
- 成员增加：https://api.luckylillia.com/schema-189483976.md
- 成员减少：https://api.luckylillia.com/schema-189483975.md
- 获取群列表（实施恢复路径前在线核对）：https://api.luckylillia.com/api-120761715.md
- OneBot v11标准：https://github.com/botuniverse/onebot-11/blob/master/api/public.md#set_group_add_request-处理加群请求邀请

urllib请求曾403，使用curl浏览器User-Agent成功取得单页；未编辑协议代码前已阅读。

## 确认事项

1. 只处理post_type=request、request_type=group、sub_type=invite；add是普通成员入群，不由本插件审批。
2. 邀请事件含group_id、user_id、flag；LLOneBot还定义invitor_id扩展字段。邀请者按权威字段判定并在测试固定，不能误把机器人QQ记为邀请人。
3. group_increase/group_decrease的user_id是实际加入/离开的成员；只有user_id等于self_id才更新机器人群登记。operator_id用于手动入群的来源记录，不等于成员ID。
4. set_group_add_request以flag、approve、reason处理。OneBot标准还要求sub_type（invite）；LLOneBot单页未列sub_type，但实施应保留标准参数并用隔离mock确认构造，实际后端兼容性需试运行。
5. 返回data=null不是失败；仅status=ok且retcode=0视为确定成功。超时空响应或未知状态不自动重试。失败响应与未知响应应区分。
6. 手动已入群没有远端请求flag；内部manual标识仅用于队列去重，不传入set_group_add_request。

## 数据实现进度

独立id代替旧秒级主键；flag仍唯一。kind=invite/manual，joined记录机器人在群事实，decision=approve/reject，remote_state=none/unknown/ok/failed。status=pending/processing/uncertain/approved/rejected。

processing和uncertain批准记录与active群共同预留容量；失败响应释放预留，未知结果保留供人工确认。远端成功单独持久化，本地激活、开关播种、终态同事务提交。确认移出会清除待审中的joined及过时远端成功证据。

现有秒级resolve_request接口仅兼容旧调用；存在多个候选时拒绝裁决。新业务必须使用id。待审查询包括需确认记录，调用者必须显示状态并区分可直接审批与待恢复项目。

插件、配置、QQ恢复、事件入口及群心跳限制已接入。get_group_list使用no_cache=true；仅成功响应的data列表包含目标群号才能确认入群，缺失或失败不推断批准/拒绝成功。真实QQ协议兼容仍需试运行。
