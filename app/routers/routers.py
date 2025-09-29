# app/routers/routers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app import models
from app.schemas.router import RouterCreate, RouterUpdate, RouterResponse
from app.routers.resellers import get_current_reseller
from app.utils.responses import success_response, error_response

router = APIRouter()

# ➕ tambah router baru
@router.post("", response_model=RouterResponse)
def create_router(
    payload: RouterCreate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    # Jika mgmt_ip kosong → generate otomatis unik
    if not payload.mgmt_ip:
        count = db.query(models.router.MikrotikRouter).filter_by(
            reseller_id=reseller.id
        ).count()
        payload.mgmt_ip = f"10.100.100.{count+1}"

    router_obj = models.router.MikrotikRouter(
        **payload.dict(),
        reseller_id=reseller.id
    )
    db.add(router_obj)
    db.commit()
    db.refresh(router_obj)
    return success_response(router_obj, "Router created successfully")

# 📋 daftar semua router reseller
@router.get("", response_model=List[RouterResponse])
def list_routers(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return success_response(db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).all(), "Routers retrieved successfully")

# 🔎 detail router
@router.get("/{router_id}", response_model=RouterResponse)
def get_router(router_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    router_obj = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.id == router_id,
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).first()
    if not router_obj:
        return error_response("Router not found", 404)
    return success_response(router_obj, "Router retrieved successfully")

# ✏️ update router
@router.patch("/{router_id}", response_model=RouterResponse)
def update_router(router_id: str, payload: RouterUpdate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    router_obj = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.id == router_id,
        models.router.MikrotikRouter.reseller_id == reseller.id,
        models.router.MikrotikRouter.deleted_at.is_(None)
    ).first()
    if not router_obj:
        return error_response("Router not found", 404)

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(router_obj, key, value)
    db.commit()
    db.refresh(router_obj)
    return success_response(router_obj, "Router updated successfully")

# ❌ hapus (soft delete) router
@router.delete("/{router_id}", response_model=RouterResponse)
def delete_router(
    router_id: str,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    router_obj = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.id == router_id,
        models.router.MikrotikRouter.reseller_id == reseller.id
    ).first()
    if not router_obj:
        return error_response("Router not found", 404)

    # snapshot sebelum dihapus
    response_router = RouterResponse.from_orm(router_obj)

    # hapus permanen
    db.delete(router_obj)
    db.commit()

    return success_response(response_router, "Router deleted successfully")