from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def today():
    cfg = get_settings()
    return (
        date.fromisoformat(cfg.app_test_as_of)
        if cfg.app_test_as_of
        else datetime.now(ZoneInfo(cfg.app_timezone)).date()
    )
