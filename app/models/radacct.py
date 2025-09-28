# app/models/radacct.py
from sqlalchemy import Column, String, DateTime, BigInteger, Integer
from sqlalchemy.dialects.postgresql import INET, BIGINT
from app.database import Base

class RadAcct(Base):
    __tablename__ = "radacct"

    radacctid = Column(BIGINT, primary_key=True, autoincrement=True)
    username = Column(String)
    nasipaddress = Column(INET)
    framedipaddress = Column(INET)
    acctstarttime = Column(DateTime(timezone=True))
    acctstoptime = Column(DateTime(timezone=True))
    acctsessiontime = Column(Integer)
    acctinputoctets = Column(BigInteger)
    acctoutputoctets = Column(BigInteger)
    acctterminatecause = Column(String)
