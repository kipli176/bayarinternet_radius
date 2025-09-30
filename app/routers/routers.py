# app/routers/routers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import requests
import re

from app.database import get_db
from app import models
from app.schemas.router import RouterCreate, RouterUpdate, RouterResponse
from app.routers.resellers import get_current_reseller
from app.utils.responses import success_response, error_response
router = APIRouter()

# ➕ tambah router baru

def normalize_reseller_name(name: str) -> str:
    # ganti spasi & non-alfanumerik jadi underscore, lalu lowercase
    return re.sub(r'\W+', '_', name).lower()

# ➕ tambah router baru
@router.post("", response_model=dict)  # ganti response_model ke dict bebas
def create_router(
    payload: RouterCreate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    # Hitung jumlah router reseller → untuk suffix username
    count = db.query(models.router.MikrotikRouter).filter_by(
        reseller_id=reseller.id
    ).count()

    reseller_name = normalize_reseller_name(reseller.name)
    ppp_username = f"{reseller_name}_r{count+1}"

    # Tentukan remote-address unik (mgmt_ip)
    existing_ips = [
        str(r.mgmt_ip) for r in db.query(models.router.MikrotikRouter).filter_by(
            reseller_id=reseller.id
        ).all()
    ]
    base = "10.100.100."
    for i in range(2, 255):
        candidate = f"{base}{i}"
        if candidate not in existing_ips:
            remote_address = candidate
            break
    else:
        return error_response("No available remote-address for router", 400)

    # Local address = IP Mikrotik (pakai payload.mgmt_ip kalau diisi, default 192.168.88.1)
    local_address = payload.mgmt_ip or "192.168.88.1"

    # Password standar
    ppp_password = "12345678"

    # Call Mikrotik REST API untuk buat PPP secret
    try:
        resp = requests.put(
            f"http://203.190.43.51:81/rest/ppp/secret",
            auth=("admin", "rahasia"),
            json={
                "name": ppp_username,
                "password": ppp_password,
                "service": "l2tp",
                "local-address": local_address,
                "remote-address": remote_address,
                "profile": "default"
            },
            verify=False,  # karena sertifikat Mikrotik self-signed
            timeout=5
        )
        resp.raise_for_status()

    except Exception as e:
        return error_response(f"Failed to create PPP secret on Mikrotik: {e}", 500)

    # Simpan router ke DB, mgmt_ip diisi remote-address
    router_obj = models.router.MikrotikRouter(
        name=payload.name,
        reseller_id=reseller.id,
        mgmt_ip=remote_address,
        radius_secret=payload.radius_secret,
        router_identity=payload.router_identity,
    )
    db.add(router_obj)
    db.commit()
    db.refresh(router_obj)

    return success_response(
        {
            "router": RouterResponse.from_orm(router_obj),
            "ppp_username": ppp_username,
            "ppp_password": ppp_password
        },
        "Router created successfully"
    )


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