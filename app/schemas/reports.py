from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

class ResellerReportResponse(BaseModel):
    reseller_id: UUID
    reseller_name: str
    total_users: int
    active_users: int
    suspended_users: int
    total_routers: int
    invoices_draft: int
    invoices_paid: int
    invoices_overdue: int
    total_revenue: float
    last_invoice_date: Optional[datetime]

    class Config:
        orm_mode = True

class UserInvoiceSummary(BaseModel):
    id: str
    status: str
    amount: float
    period_start: datetime
    period_end: datetime

    class Config:
        orm_mode = True


class UserUsageSummary(BaseModel):
    total_sessions: int
    total_bytes_in: int
    total_bytes_out: int
    last_session_start: Optional[datetime]
    last_session_stop: Optional[datetime]


class UserReportResponse(BaseModel):
    user_id: str
    username: str
    full_name: Optional[str]
    phone: Optional[str]
    status: str
    active_until: Optional[date]
    invoices: List[UserInvoiceSummary]
    usage: UserUsageSummary

class SystemReportResponse(BaseModel):
    total_resellers: int
    total_users: int
    active_users: int
    suspended_users: int
    total_invoices: int
    invoices_paid: int
    invoices_overdue: int
    total_revenue: float

    class Config:
        orm_mode = True
