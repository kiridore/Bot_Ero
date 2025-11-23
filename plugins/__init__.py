from .menu import MenuPlugin
from .reload import ReloadPlugin
from .checkin import CheckinPlugin
from .week_checkin_display import WeekCheckinDisplayPlugin
from .personal_records import PersonalRecords
from .week_list import WeekListPlugin
from .monitor import MonitorPlugin
from .roll_back import RollbackCheckinPlugin
from .call import CallPlugin
from .update import UpdatePlugin
from .auto_friend import AutoFriendPlugin
from .welcome import WelcomePlugin
from .all_checkin_display import AllCheckinDisplay
from .backup import BackupPlugin
from .read_history import HistoryPlugin
from .set_group_title import GroupSpecialTitlePlugin

__all__ = []
__all__.append("MenuPlugin")
# __all__.append("ReloadPlugin")    # 重载后会导致内存里有多个Plugin子类，暂时关闭
__all__.append("CheckinPlugin")
__all__.append("WeekCheckinDisplayPlugin")
__all__.append("PersonalRecords")
__all__.append("WeekListPlugin")
__all__.append("MonitorPlugin")
__all__.append("RollbackCheckinPlugin")
__all__.append("CallPlugin")
__all__.append("UpdatePlugin")
__all__.append("AutoFriendPlugin")
__all__.append("WelcomePlugin")
__all__.append("AllCheckinDisplay")
__all__.append("BackupPlugin")
# __all__.append("HistoryPlugin")
# __all__.append("GroupSpecialTitlePlugin")
