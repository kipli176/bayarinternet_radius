# app/schemas/invoice.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
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
    currency: str = "IDR"
    meta: Optional[Dict[str, Any]]

class InvoiceCreate(BaseModel):
    period_start: datetime
    period_end: datetime

class InvoiceUpdate(BaseModel):
    status: Optional[str]

class InvoiceResponse(InvoiceBase):
    id: UUID
    reseller_id: UUID
    status: str
    created_at: datetime

    class Config:
        orm_mode = True
