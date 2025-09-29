import uuid
from sqlalchemy import Column, String, Boolean, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from .mixins import TimestampMixin, SoftDeleteMixin


class Reseller(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "resellers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)                     # nama kontak/reseller
    company_name = Column(String)                             # nama perusahaan
    email = Column(String, unique=True, nullable=False)       # DB pakai CITEXT
    phone = Column(String)
    alamat = Column(Text)                                     # alamat perusahaan
    logo = Column(String)                                     # URL/path logo

    password_hash = Column(String, nullable=False)

    price_per_user = Column(Numeric(12, 2), nullable=False, default=500)  # default 500
    currency = Column(String, nullable=False, default="IDR")
    volume_pricing = Column(JSONB, nullable=True)             # default di DB {"100":0.1,"200":0.2,"500":0.3}

    is_active = Column(Boolean, nullable=False, default=True)
