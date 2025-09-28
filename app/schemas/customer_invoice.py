# app/schemas/customer_invoice.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class CustomerInvoiceBase(BaseModel):
    period_start: datetime
    period_end: datetime
    amount: float
    status: Optional[str] = "draft"

class CustomerInvoiceCreate(CustomerInvoiceBase):
    user_id: UUID
    profile_id: UUID

class CustomerInvoiceUpdate(BaseModel):
    status: Optional[str]

class CustomerInvoiceResponse(CustomerInvoiceBase):
    id: UUID
    reseller_id: UUID
    user_id: UUID
    profile_id: Optional[UUID]
    meta: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
