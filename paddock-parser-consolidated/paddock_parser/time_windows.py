# time_windows.py
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

from .config_manager import config_manager


def within_business_hours() -> bool:
    config = config_manager.get_config()
    http_client_config = config.get("HTTP_CLIENT", {})

    tz = http_client_config.get("biz_hours_local_tz", "UTC")
    start_h = int(http_client_config.get("biz_hours_start", 8))
    end_h = int(http_client_config.get("biz_hours_end", 22))
    now = datetime.now(ZoneInfo(tz))
    return start_h <= now.hour < end_h
