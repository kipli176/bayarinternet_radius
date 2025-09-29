from sqlalchemy import Column, String, Numeric, Integer, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base

class PPPProfile(Base):
    __tablename__ = "ppp_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)

    rate_limit_up = Column(Text)
    rate_limit_down = Column(Text)
    burst_limit_up = Column(Text)
    burst_limit_down = Column(Text)
    burst_threshold_up = Column(Text)
    burst_threshold_down = Column(Text)
    burst_time_up = Column(Integer)
    burst_time_down = Column(Integer)
    min_rate_up = Column(Text)
    min_rate_down = Column(Text)

    priority = Column(Integer, default=8)
    group_name = Column(Text)
    auto_pool = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
