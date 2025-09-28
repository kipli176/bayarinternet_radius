from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PaymentBase(BaseModel):
    invoice_id: int
    amount: float
    method: str

class PaymentCreate(PaymentBase):
    pass

class PaymentResponse(PaymentBase):
    id: int
    status: str
    provider_txn_id: Optional[str]
    paid_at: Optional[datetime]

    class Config:
        orm_mode = True
