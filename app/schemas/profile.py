from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

# 👉 Base schema untuk shared field
class PPPProfileBase(BaseModel):
    name: str
    price: float

    rate_limit_up: Optional[str] = None
    rate_limit_down: Optional[str] = None
    burst_limit_up: Optional[str] = None
    burst_limit_down: Optional[str] = None
    burst_threshold_up: Optional[str] = None
    burst_threshold_down: Optional[str] = None
    burst_time_up: Optional[int] = None
    burst_time_down: Optional[int] = None
    min_rate_up: Optional[str] = None
    min_rate_down: Optional[str] = None
    priority: Optional[int] = 8
    group_name: Optional[str] = None
    auto_pool: Optional[bool] = True
    is_active: Optional[bool] = True


# 👉 Create schema
class PPPProfileCreate(PPPProfileBase):
    pass


# 👉 Update schema (partial update)
class PPPProfileUpdate(BaseModel):
    name: Optional[str]
    price: Optional[float]
    rate_limit_up: Optional[str]
    rate_limit_down: Optional[str]
    burst_limit_up: Optional[str]
    burst_limit_down: Optional[str]
    burst_threshold_up: Optional[str]
    burst_threshold_down: Optional[str]
    burst_time_up: Optional[int]
    burst_time_down: Optional[int]
    min_rate_up: Optional[str]
    min_rate_down: Optional[str]
    priority: Optional[int]
    group_name: Optional[str]
    auto_pool: Optional[bool]
    is_active: Optional[bool]


# 👉 Response schema
class PPPProfileResponse(PPPProfileBase):
    id: UUID
    reseller_id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        orm_mode = True
