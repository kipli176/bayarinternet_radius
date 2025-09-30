# app/models/nas_status_log.py
import uuid
from sqlalchemy import Column, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from datetime import datetime

class NasStatusLog(Base):
    __tablename__ = "nas_status_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    router_id = Column(UUID(as_uuid=True), ForeignKey("mikrotik_routers.id", ondelete="CASCADE"), nullable=False)
    status = Column(Text, nullable=False)   # "ok" / "fail"
    message = Column(Text)
    checked_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
