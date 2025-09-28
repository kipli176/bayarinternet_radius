from pydantic import BaseModel
from datetime import datetime

class SessionResponse(BaseModel):
    username: str
    nas_ip: str
    framed_ip: str
    start_time: datetime
    uptime: int
    bytes_in: int
    bytes_out: int
