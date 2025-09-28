# app/models/audit.py
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, BIGINT
from app.database import Base
from .mixins import TimestampMixin

class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    reseller_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="SET NULL"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("ppp_users.id", ondelete="SET NULL"))
    actor_id = Column(UUID(as_uuid=True), ForeignKey("resellers.id", ondelete="SET NULL"))

    action = Column(String, nullable=False)
    details = Column(JSONB)   # bisa simpan data lama/baru, alasan, dsb
