import uuid
from sqlalchemy import Column, Integer, Numeric, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.database import Base
from .mixins import TimestampMixin


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    reseller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resellers.id", ondelete="CASCADE"),
        nullable=False
    )

    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    users_count = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(14, 2), nullable=False)

    discount = Column(Numeric(14, 2), nullable=False, default=0)
    tax = Column(Numeric(14, 2), nullable=False, default=0)
    total = Column(Numeric(14, 2), nullable=False)

    currency = Column(Text, nullable=False, default="IDR")
    status = Column(ENUM(name="invoice_status", create_type=False), nullable=False, default="draft")
    meta = Column(JSON, nullable=True)
