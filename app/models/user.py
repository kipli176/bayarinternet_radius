# app/models/user.py
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

class PPPUser(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ppp_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("ppp_profiles.id", ondelete="SET NULL"))

    username = Column(String, nullable=False)           # unik per reseller
    password_hash = Column(String, nullable=False)

    full_name = Column(String)
    email = Column(String)
    phone = Column(String)

    status = Column(String, nullable=False, default="active")   # active, suspended, expired
    active_until = Column(DateTime(timezone=True))              # expiry date

    suspended = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("reseller_id", "username", name="uq_pppuser_reseller_username"),
    )
