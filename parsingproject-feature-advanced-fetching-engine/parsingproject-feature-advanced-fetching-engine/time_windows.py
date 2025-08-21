# time_windows.py
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

from config import HTTP as HTTP_CFG

def within_business_hours() -> bool:
    tz = HTTP_CFG.get("biz_hours_local_tz", "UTC")
    start_h = int(HTTP_CFG.get("biz_hours_start", 8))
    end_h = int(HTTP_CFG.get("biz_hours_end", 22))
    now = datetime.now(ZoneInfo(tz))
    return start_h <= now.hour < end_h
