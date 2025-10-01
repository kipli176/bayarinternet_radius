# app/schemas/customer_invoice.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal

class CustomerInvoiceBase(BaseModel):
    period_start: date
    period_end: date
    amount: Decimal

class CustomerInvoiceCreate(BaseModel):
    user_id: UUID
    months: int = 1                          # default 1 bulan
    period_start: Optional[date] = None  # opsional; kalau None dihitung otomatis
    meta: Optional[dict] = None              # detail untuk nota (opsional)

class CustomerInvoiceUpdate(BaseModel):
    status: Optional[str] = None
    paid_at: Optional[datetime] = None

class CustomerInvoiceResponse(CustomerInvoiceBase):
    id: UUID
    reseller_id: UUID
    user_id: UUID
    profile_id: UUID
    status: str
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        orm_mode = True