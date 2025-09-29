from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from uuid import UUID


class InvoiceBase(BaseModel):
    period_start: datetime
    period_end: datetime
    users_count: int
    unit_price: float
    subtotal: float
    discount: Optional[float] = 0
    tax: Optional[float] = 0
    total: float
    currency: Optional[str] = "IDR"
    status: Optional[str] = "draft"   # langsung string enum dari DB
    meta: Optional[Any] = None        # snapshot reseller info


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    status: Optional[str] = None


class InvoiceResponse(InvoiceBase):
    id: UUID
    reseller_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
