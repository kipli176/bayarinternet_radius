# app/models/customer_invoice.py
import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from .mixins import TimestampMixin

class CustomerInvoice(Base, TimestampMixin):
    __tablename__ = "customer_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    reseller_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("ppp_users.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("ppp_profiles.id", ondelete="SET NULL"), nullable=False)

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="unpaid")   # draft, sent, paid, overdue
    meta = Column(JSONB)
    paid_at = Column(DateTime(timezone=True), nullable=True)
