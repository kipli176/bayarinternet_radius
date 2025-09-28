from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class ProfileBase(BaseModel):
    name: str
    price: float
    group_name: Optional[str]
    rate_limit_up: Optional[str]
    rate_limit_down: Optional[str]
    burst_limit_up: Optional[str]
    burst_limit_down: Optional[str]
    burst_threshold_up: Optional[str]
    burst_threshold_down: Optional[str]
    burst_time_up: Optional[str]
    burst_time_down: Optional[str]
    priority: Optional[int]
    auto_pool: Optional[bool] = False

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    name: Optional[str]
    price: Optional[float]
    group_name: Optional[str]
    rate_limit_up: Optional[str]
    rate_limit_down: Optional[str]
    burst_limit_up: Optional[str]
    burst_limit_down: Optional[str]
    burst_threshold_up: Optional[str]
    burst_threshold_down: Optional[str]
    burst_time_up: Optional[str]
    burst_time_down: Optional[str]
    priority: Optional[int]
    auto_pool: Optional[bool]
    is_active: Optional[bool]

class ProfileResponse(ProfileBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True
