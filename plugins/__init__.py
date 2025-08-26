from .menu import MenuPlugin
from .reload import ReloadPlugin
from .checkin import CheckinPlugin
from .week_checkin_display import WeekCheckinDisplayPlugin
from .personal_records import PersonalRecords
from .week_list import WeekListPlugin
from .monitor import MonitorPlugin
from .roll_back import RollbackCheckinPlugin
from .call import CallPlugin
from .restart import RestartPlugin

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
__all__.append("RestartPlugin")

