# app/schemas/customer_invoice.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class CustomerInvoiceBase(BaseModel):
    period_start: datetime
    period_end: datetime
    amount: Decimal

class CustomerInvoiceCreate(CustomerInvoiceBase):
    user_id: UUID
    period_start: datetime
    period_end: datetime
    amount: Decimal

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