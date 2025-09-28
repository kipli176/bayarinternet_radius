# app/routers/routers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app import models
from app.schemas.router import RouterCreate, RouterUpdate, RouterResponse
from app.routers.resellers import get_current_reseller

router = APIRouter()

# ➕ tambah router baru
@router.post("/", response_model=RouterResponse)
def create_router(payload: RouterCreate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    router_obj = models.router.MikrotikRouter(
        reseller_id=reseller.id,
        name=payload.name,
        router_identity=payload.router_identity,
        mgmt_ip=payload.mgmt_ip,
        radius_secret=payload.radius_secret,
        is_active=True,
    )
    db.add(router_obj)
    db.commit()
    db.refresh(router_obj)
    return router_obj

# 📋 daftar semua router reseller
@router.get("/", response_model=List[RouterResponse])
def list_routers(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).all()

# 🔎 detail router
@router.get("/{router_id}", response_model=RouterResponse)
def get_router(router_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    router_obj = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.id == router_id,
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router not found")
    return router_obj

# ✏️ update router
@router.patch("/{router_id}", response_model=RouterResponse)
def update_router(router_id: str, payload: RouterUpdate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    router_obj = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.id == router_id,
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(router_obj, key, value)
    db.commit()
    db.refresh(router_obj)
    return router_obj

# ❌ hapus (soft delete) router
@router.delete("/{router_id}")
def delete_router(router_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    router_obj = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.id == router_id,
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router not found")

    router_obj.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "Router deleted"}
