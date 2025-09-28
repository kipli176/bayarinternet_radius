from pydantic import BaseModel
from datetime import datetime 

class AuthLogResponse(BaseModel):
    id: int
    username: str
    reply: str
    authdate: datetime 

class AccountingLogResponse(BaseModel):
    username: str
    nas_ip: str
    framed_ip: str
    start_time: datetime
    stop_time: datetime
    bytes_in: int
    bytes_out: int
    terminate_cause: str
