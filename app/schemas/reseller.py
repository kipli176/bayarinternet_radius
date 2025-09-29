from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

class ResellerBase(BaseModel):
    name: str
    company_name: Optional[str]        # ✅ baru
    email: EmailStr
    phone: Optional[str]
    alamat: Optional[str]              # ✅ baru
    logo: Optional[str]                # ✅ baru
    price_per_user: float = 500        # ✅ default
    currency: str = "IDR"
    volume_pricing: Optional[Dict[str, Any]]

class ResellerCreate(ResellerBase):
    password: str

class ResellerUpdate(BaseModel):
    name: Optional[str]
    company_name: Optional[str]        # ✅ baru
    email: Optional[EmailStr]
    phone: Optional[str]
    alamat: Optional[str]              # ✅ baru
    logo: Optional[str]                # ✅ baru
    price_per_user: Optional[float]
    currency: Optional[str]
    volume_pricing: Optional[Dict[str, Any]]
    is_active: Optional[bool]

class ResellerResponse(ResellerBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True
        
class ResellerSummary(BaseModel):
    total_users: int
    total_routers: int
    last_invoice_id: Optional[str]
