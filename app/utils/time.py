from datetime import datetime, date
from calendar import monthrange
import pytz

def utc_now():
    return datetime.utcnow()

def to_wib(dt: datetime):
    tz = pytz.timezone("Asia/Jakarta")
    return dt.astimezone(tz) 


def add_months_keep_dom(dt: date, months: int = 1) -> date:
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    last_day = monthrange(y, m)[1]
    d = min(dt.day, last_day)
    return dt.replace(year=y, month=m, day=d)