"""结构化菜单条目：每行指令带插件归属与权限，渲染时按当前位置有效插件过滤。

文案包可逐条覆盖：键 `menu.<指令词>`（如 menu./打卡）替换该行文字，
但条目是否显示仍由插件归属、权限和有效开关决定——文字覆盖不能改变可见性。
"""
from core.config import NICKNAME
from core.text_pack import get_text

# (整行文案, 插件标识或 None=始终显示, admin=仅超级用户, group_only=仅群聊显示)
通用 = [
    ("/菜单 查看菜单", "menu", False, False),
    ("/注册 开始注册（新用户）", "register", False, False),
    ("/打卡 + 图片 完成打卡", "checkin", False, False),
    ("/档案 [年份] 查看个人打卡档案", "personal_records", False, False),
    ("/本周打卡图 查看本周打卡图", "week_checkin_display", False, False),
    ("/ALL 查看全量打卡图统计", "all_checkin_display", False, False),
    ("/补卡 [YYYY-MM-DD] 周补卡（4点）", "remedy_checkin", False, False),
    ("/单日补卡 [YYYY-MM-DD] 单日补卡（2点）", "remedy_checkin", False, False),
    ("/撤回打卡 撤回本周最近一次打卡", "roll_back", False, False),
    ("/周常 查看本周任务进度", "weekly_quest", False, False),
    ("/抽奖 或 /抽卡 消耗积分抽奖（每日次数与打卡状态相关）", "lottery", False, False),
    ("/一键抽奖 连续抽完今日剩余抽奖次数，合并转发所有结果", "lottery", False, False),
    ("/抽卡消费 [@用户] 查询累计抽卡消费积分", "lottery", False, False),
    ("/仙人彩 [四位数字] 查看本期奖池与注单；带号码则下注（同 下注 XXXX，每日 1 注，周日 20:00 开奖）", "immortal_lottery", False, False),
    ("/随机参考 随机图片参考（512x512）", "random_reference", False, False),
    ("/占卜 抽塔罗牌（含正位/逆位）", "divination", False, False),
    (".r [表达式] [原因] 万能骰点（空=D100，支持 +-*/() #多轮 d优势/劣势）", "trpg_dice", False, False),
    (".rc [优势|劣势] <属性/表达式> [豁免] DND检定（例：.rc 力量 / .rc 优势 侦查 / .rc 体质 豁免）", "trpg_dice", False, False),
    (".rh [表达式] [原因] 暗骰（群聊提示，私聊结果）", "trpg_dice", False, False),
    ("/跑团记录 开始 开始录制跑团聊天", "trpg_session", False, False),
    ("/跑团记录 强制开始 强制开始（丢弃未导出记录）", "trpg_session", False, False),
    ("/跑团记录 结束 结束录制并合并转发", "trpg_session", False, False),
    ("/跑团记录 导出 将完成的记录保存到磁盘", "trpg_session", False, False),
    ("/跑团记录 列表 查看已保存的记录列表", "trpg_session", False, False),
    ("/跑团记录 #N 查看某次记录的概要信息", "trpg_session", False, False),
    ("/角色 查看 查看我的当前角色卡", "trpg_char", False, False),
    ("/角色 切换 <编号> 切换当前角色", "trpg_char", False, False),
    ("/角色 列表 列出我的角色", "trpg_char", False, False),
    ("/角色 删除 <编号> 删除角色", "trpg_char", False, False),
    ("/角色 创建/编辑 网页端车卡：https://littlero.tech/trpg", "trpg_char", False, False),
    (".rc 可使用角色属性/技能值；.r 力量 或 .r 侦查+10 引用角色属性", "trpg_char", False, False),
    ("/排名 或 /rank 查看积分排行榜", "leaderboard", False, False),
    ("/商店 [商品id] 积分商店（无参数列出本周货架，每周一 8:00 刷新）", "redeem_shop", False, False),
    ("/兑换码 <兑换码> 使用兑换码兑换奖励（格式 XXXX-XXXX-XXXX）", "redeem_code", False, False),
    ("/FF新闻 FF14 国服官网近期新闻", "ff_news", False, False),
    ("/称号 查看称号系统帮助", "title", False, False),
    ("/称号一览 查看已解锁称号", "title", False, False),
    ("/称号 当前 查看当前装备称号", "title", False, False),
    ("/称号 <index> 装备称号", "title", False, False),
    ("/称号 卸下 取消装备称号", "title", False, False),
    ("/称号 详情 <index> 查看称号说明", "title", False, False),
    ("/称号 随机 随机装备一个已解锁称号", "title", False, False),
    ("/称号 查看 @用户 查看他人称号", "title", False, False),
    ("/创建游戏 <类型> [人数] 群聊创建游戏房间，类型：卧底（默认6人，4-10人）", "who_is_spy", False, True),
    ("/开始 <房间号> 群聊开始游戏", "who_is_spy", False, True),
    ("/加入 <房间号> 私聊加入游戏房间", "who_is_spy", False, False),
    ("/离开 私聊退出房间（仅等待阶段）", "who_is_spy", False, False),
    ("/退出 私聊退出房间（游戏中弃权出局）", "who_is_spy", False, False),
    ("/状态 [房间号] 查看房间信息", "who_is_spy", False, False),
    ("/放弃 <房间号> 群聊解散房间（房主/超管）", "who_is_spy", False, True),
    ("/房间列表 群聊查看本群所有活跃房间", "who_is_spy", False, True),
    ("/游戏记录 [房间号] 群聊查看已保存的游戏记录列表或详情", "who_is_spy", False, True),
    ("/活动 创建 接龙 <标题> [描述] [参数]   发布接龙（参数：限时/报名截止/截止，如：限时 2天 报名截止 2026-08-10 20:00）", "activity", False, True),
    ("/活动 创建 匹配 <标题> [描述] [参数]   发布匹配（必填 截止 <时间>，可选 报名截止）", "activity", False, True),
    ("/活动 创建 征集 <标题> [描述] [参数] 截止 <时间>   发布征集（必填 截止，可选 报名截止；各自提交一次作品）", "activity", False, True),
    ("/活动 加入 [编号] / 退出 [编号] 报名 / 退出活动（多活动并行时需带编号）", "activity", False, False),
    ("/活动 开始 [编号] 开始活动（创建人）", "activity", False, False),
    ("/活动 状态 [编号] / 结束 [编号] 查看进度（多个活动时列出编号）/ 结束活动", "activity", False, False),
    ("/提交 [活动id] （私聊）提交作品（重复提交覆盖）", "activity", False, False),
    (f"{NICKNAME} 召唤机器人", "call", False, False),
]

群聊 = [
    ("/本周板油 查看本周打卡成员", "week_list", False),
    ("/闹钟 … 定时提醒（仅发 /闹钟 可看完整用法；/闹钟 一览 / /闹钟 取消 <编号>）", "group_alarm", False),
    ("/群头衔 [文本] 设置群头衔（留空为取消）", "set_group_title", False),
    ("回复一条消息并发送 /全体成员 可@全体并转发该消息内容", "at_all_reply", False),
    ("回复自己发的某条消息并发送 /撤回 可让小埃代为撤回那条消息", "recall_message", False),
    ("回复某条消息并发送 /加精 /群精华 /精华 设为群精华", "group_essence", False),
    ("回复某条消息并发送 /删除精华 取消该条消息的群精华", "group_essence", False),
]

管理 = [
    ("/超级补卡 YYYY-MM-DD [user_id] 免扣点补整周", "remedy_checkin", True),
    ("/超级单日补卡 YYYY-MM-DD [user_id] 免扣点补单日", "remedy_checkin", True),
    ("/发金币 <数量> 给所有用户统一发积分", "grant_points_all", True),
    ("/刷新商店 立刻刷新积分商店货架", "redeem_shop", True),
    ("/数据备份 手动执行备份", "backup", True),
    ("/系统状态 查看运行状态（超级用户）", "monitor", True),
    ("/更新 拉取更新并重启（超级用户）", "update", True),
    ("/插件 <name|列表> [off] [群号] 管理插件：列表/启用/禁用（超级用户）", "group_manager", True),
    ("/功能包 <name|列表> [off] [群号] 管理功能包：列表/开启/关闭（超级用户）", "group_manager", True),
    ("/插件 <name> <开启|关闭|默认> 用户 <账号> 设置该账号的私聊插件（超级用户）", "group_manager", True),
    ("/功能包 <name> <开启|关闭|默认> 用户 <账号> 批量设置该账号的私聊插件（超级用户）", "group_manager", True),
    ("/插件 列表 用户 <账号> 查看账号设置；/功能包 列表 用户 <账号> 查看账号功能包", "group_manager", True),
    ("两条管理指令均可用 <name> <开启|关闭> 群 <群号> 明确指定群", None, True),
    ("默认：恢复沿用私聊公共设置；系统插件不能关闭", None, True),
    ("不指定目标时，私聊修改私聊公共设置，群聊修改本群设置", None, True),
]

SECTIONS = (
    ("【通用指令】", [(line, plugin, admin, group) for line, plugin, admin, group in 通用]),
    ("【群聊功能】", [(line, plugin, admin, False) for line, plugin, admin in 群聊]),
    ("【管理员指令】", [(line, plugin, admin, False) for line, plugin, admin in 管理]),
)


def _entry_line(line: str) -> str:
    """文案包逐条覆盖：menu.<指令词> 替换文字，不改变归属与权限。"""
    token = line.split(" ", 1)[0] if line.startswith(("/", ".")) else ""
    if token:
        return get_text(f"menu.{token}", line)
    return line


def _visible(entry, enabled, is_super, in_group):
    _, plugin, admin, group_only = entry
    if admin and not is_super:
        return False
    if group_only and not in_group:
        return False
    if plugin is None:
        return True
    return bool(enabled.get(plugin, False))


def render_menu(enabled, is_super: bool, in_group: bool) -> str:
    """按当前位置有效插件集合渲染菜单；管理员段仅超级用户可见。"""
    lines = [f"{NICKNAME}指令菜单", "---------------------------"]
    for title, entries in SECTIONS:
        visible = [e for e in entries if _visible(e, enabled, is_super, in_group)]
        if visible:
            lines.append(title)
            lines.extend(_entry_line(e[0]) for e in visible)
    return "\n".join(lines)
