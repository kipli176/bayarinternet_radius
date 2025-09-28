# app/routers/resellers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models
from app.schemas.reseller import ResellerResponse, ResellerUpdate, ResellerSummary
from app.utils.security import decode_access_token
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_reseller(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    reseller = db.query(models.reseller.Reseller).filter(models.reseller.Reseller.id == payload.get("sub")).first()
    if not reseller:
        raise HTTPException(status_code=401, detail="Reseller not found")
    return reseller

# detail reseller
@router.get("/{reseller_id}", response_model=ResellerResponse)
def get_reseller(reseller_id: str, db: Session = Depends(get_db)):
    reseller = db.query(models.reseller.Reseller).filter(models.reseller.Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    return reseller

# update reseller
@router.patch("/{reseller_id}", response_model=ResellerResponse)
def update_reseller(reseller_id: str, payload: ResellerUpdate, db: Session = Depends(get_db)):
    reseller = db.query(models.reseller.Reseller).filter(models.reseller.Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(reseller, key, value)
    db.commit()
    db.refresh(reseller)
    return reseller

# summary reseller
@router.get("/{reseller_id}/summary", response_model=ResellerSummary)
def reseller_summary(reseller_id: str, db: Session = Depends(get_db)):
    reseller = db.query(models.reseller.Reseller).filter(models.reseller.Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")

    total_users = db.query(models.user.PPPUser).filter(models.user.PPPUser.reseller_id == reseller_id).count()
    total_routers = db.query(models.router.MikrotikRouter).filter(models.router.MikrotikRouter.reseller_id == reseller_id).count()
    last_invoice = db.query(models.invoice.Invoice).filter(models.invoice.Invoice.reseller_id == reseller_id).order_by(models.invoice.Invoice.created_at.desc()).first()

    return {
        "total_users": total_users,
        "total_routers": total_routers,
        "last_invoice_id": str(last_invoice.id) if last_invoice else None
    }
