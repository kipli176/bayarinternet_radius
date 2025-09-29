# app/schemas/invoice.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict
from decimal import Decimal
from uuid import UUID

class InvoiceBase(BaseModel):
    period_start: datetime
    period_end: datetime

class InvoiceCreate(InvoiceBase):
    """dipakai saat generate invoice"""
    # secara teknis bisa saja banyak field,
    # tapi di endpoint /generate hanya period_start & period_end yang dipakai
    pass

class InvoiceResponse(InvoiceBase):
    id: UUID
    reseller_id: UUID
    users_count: int
    unit_price: Decimal
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    currency: str
    status: str
    meta: Optional[Dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
