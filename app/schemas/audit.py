from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class AuditLogResponse(BaseModel):
    id: int
    reseller_id: str
    user_id: Optional[str]
    actor_id: Optional[str]
    action: str
    details: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        orm_mode = True
