from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def today():
    return datetime.now(ZoneInfo(get_settings().app_timezone)).date()
