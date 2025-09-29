import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET
from app.database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

class MikrotikRouter(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "mikrotik_routers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reseller_id = Column(UUID(as_uuid=True), 
                         ForeignKey("resellers.id", ondelete="CASCADE"), 
                         nullable=False)

    name = Column(String, nullable=False)
    router_identity = Column(String)
    mgmt_ip = Column(INET, nullable=False)
    radius_secret = Column(String, nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)  # ✅ tetap dipakai
