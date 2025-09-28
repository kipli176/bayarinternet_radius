# app/models/radpostauth.py
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import BIGINT, INET
from app.database import Base

class RadPostAuth(Base):
    __tablename__ = "radpostauth"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    username = Column(String)
    pass_field = Column("pass", String)   # kolom bernama "pass" di DB
    reply = Column(String)
    authdate = Column(DateTime(timezone=True)) 
