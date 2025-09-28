# app/models/reseller.py
import uuid
from sqlalchemy import Column, String, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from .mixins import TimestampMixin

class Reseller(Base, TimestampMixin):
    __tablename__ = "resellers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)     # DB pakai CITEXT, String di ORM ok
    phone = Column(String)
    # kredensial login reseller disimpan sebagai hash
    password_hash = Column(String, nullable=False)

    price_per_user = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False, default="IDR")
    volume_pricing = Column(JSONB)                          # skema diskon bertingkat (opsional)
    is_active = Column(Boolean, nullable=False, default=True)
