from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import models
from app.schemas.logs import AuthLogResponse, AccountingLogResponse
from app.routers.resellers import get_current_reseller

router = APIRouter()

# 🔐 logs dari radpostauth (hasil autentikasi)
@router.get("/auth", response_model=List[AuthLogResponse])
def get_auth_logs(
    username: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filter reply, e.g. Access-Reject"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    global_logs: bool = Query(False, alias="global", description="Tampilkan semua log tanpa filter reseller"),
    limit: int = Query(100, ge=1, le=1000, description="Jumlah maksimal hasil (default 100, max 1000)"),
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller),
):
    q = db.query(models.radpostauth.RadPostAuth)

    if not global_logs:
        q = (
            q.join(models.user.PPPUser, models.radpostauth.RadPostAuth.username == models.user.PPPUser.username)
            .filter(models.user.PPPUser.reseller_id == reseller.id)
        )

    if username:
        q = q.filter(models.radpostauth.RadPostAuth.username == username)
    if status:
        q = q.filter(models.radpostauth.RadPostAuth.reply == status)
    if date_from:
        q = q.filter(models.radpostauth.RadPostAuth.authdate >= date_from)
    if date_to:
        q = q.filter(models.radpostauth.RadPostAuth.authdate <= date_to)

    rows = q.order_by(models.radpostauth.RadPostAuth.authdate.desc()).limit(limit).all()

    return [
        AuthLogResponse(
            id=r.id,
            username=r.username,
            reply=r.reply,
            authdate=r.authdate,
            nas_ip=getattr(r, "nas_ip", None) or "Unknown",
        )
        for r in rows
    ]


# 📊 logs dari radacct (accounting session)
@router.get("/accounting", response_model=List[AccountingLogResponse])
def get_accounting_logs(
    username: Optional[str] = Query(None),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    global_logs: bool = Query(False, alias="global", description="Tampilkan semua log tanpa filter reseller"),
    limit: int = Query(100, ge=1, le=1000, description="Jumlah maksimal hasil (default 100, max 1000)"),
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller),
):
    q = db.query(models.radacct.RadAcct)

    if not global_logs:
        q = (
            q.join(models.user.PPPUser, models.radacct.RadAcct.username == models.user.PPPUser.username)
            .filter(models.user.PPPUser.reseller_id == reseller.id)
        )

    if username:
        q = q.filter(models.radacct.RadAcct.username == username)
    if date_from:
        q = q.filter(models.radacct.RadAcct.acctstarttime >= date_from)
    if date_to:
        q = q.filter(models.radacct.RadAcct.acctstarttime <= date_to)

    rows = q.order_by(models.radacct.RadAcct.acctstarttime.desc()).limit(limit).all()

    return [
        AccountingLogResponse(
            username=r.username,
            nas_ip=r.nasipaddress,
            framed_ip=r.framedipaddress,
            start_time=r.acctstarttime,
            stop_time=r.acctstoptime or datetime(1970, 1, 1),
            bytes_in=r.acctinputoctets or 0,
            bytes_out=r.acctoutputoctets or 0,
            terminate_cause=r.acctterminatecause or "Unknown",
        )
        for r in rows
    ]
