# app/models/profile.py
import uuid
from sqlalchemy import Column, String, Boolean, Numeric, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

class PPPProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ppp_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)                   # nama profil
    group_name = Column(String)                             # optional: binding ke profil di mikrotik

    # harga jual
    price = Column(Numeric(12, 2), nullable=False, default=0)

    # rate limit & burst config
    rate_limit_up = Column(String)        # ex: "3M"
    rate_limit_down = Column(String)      # ex: "3M"
    burst_limit_up = Column(String)
    burst_limit_down = Column(String)
    burst_threshold_up = Column(String)
    burst_threshold_down = Column(String)
    burst_time_up = Column(String)
    burst_time_down = Column(String)
    priority = Column(Integer)

    # flag auto assign pool
    auto_pool = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
