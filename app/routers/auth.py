# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app import models
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.schemas.reseller import ResellerResponse
from app.utils import security

router = APIRouter()

# register reseller baru
@router.post("/register", response_model=ResellerResponse)
def register_reseller(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.reseller.Reseller).filter(models.reseller.Reseller.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    reseller = models.reseller.Reseller(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=security.hash_password(payload.password),
        price_per_user=0,
        currency="IDR",
        is_active=True
    )
    db.add(reseller)
    db.commit()
    db.refresh(reseller)
    return reseller

# login reseller
@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    reseller = db.query(models.reseller.Reseller).filter(models.reseller.Reseller.email == payload.email).first()
    if not reseller or not security.verify_password(payload.password, reseller.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(data={"sub": str(reseller.id)}, expires_delta=access_token_expires)
    return {"access_token": token, "token_type": "bearer"}
