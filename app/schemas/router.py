from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class RouterBase(BaseModel):
    name: str
    router_identity: Optional[str]
    mgmt_ip: Optional[str] = None  
    radius_secret: str
    is_active: Optional[bool] = True   # ✅ ditambahkan

class RouterCreate(RouterBase):
    pass

class RouterUpdate(BaseModel):
    name: Optional[str]
    router_identity: Optional[str]
    radius_secret: Optional[str]
    mgmt_ip: Optional[str]     
    is_active: Optional[bool]

class RouterResponse(RouterBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True
