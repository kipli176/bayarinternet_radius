from datetime import datetime
from calendar import monthrange
import pytz

def utc_now():
    return datetime.utcnow()

def to_wib(dt: datetime):
    tz = pytz.timezone("Asia/Jakarta")
    return dt.astimezone(tz) 

def add_months_keep_dom(dt: datetime, months: int = 1) -> datetime:
    # hitung tahun & bulan baru
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    # clamp hari kalau bulan baru lebih pendek (misal 31 -> 30/28)
    last_day = monthrange(y, m)[1]
    d = min(dt.day, last_day)
    return dt.replace(year=y, month=m, day=d, hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=0)
