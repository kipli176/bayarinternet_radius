# app/models/invoice.py
import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from .mixins import TimestampMixin

class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)

    # periode tagihan
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # detail perhitungan
    users_count = Column(Integer, nullable=False, default=0)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)
    subtotal = Column(Numeric(12, 2), nullable=False, default=0)
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    tax = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False, default=0)

    currency = Column(String, nullable=False, default="IDR")
    status = Column(String, nullable=False, default="draft")   # draft, sent, paid, overdue

    # metadata tambahan (misal invoice number, notes, dsb)
    meta = Column(JSONB)
