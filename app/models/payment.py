# app/models/payment.py
from sqlalchemy import Column, String, ForeignKey, Numeric, DateTime
from sqlalchemy.dialects.postgresql import BIGINT
from app.database import Base
from .mixins import TimestampMixin

class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    invoice_id = Column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    method = Column(String, nullable=False)                  # cash, transfer, xendit, midtrans, dll
    provider_txn_id = Column(String)                         # id dari payment gateway
    status = Column(String, nullable=False, default="pending")  # pending, success, failed
    paid_at = Column(DateTime(timezone=True))
