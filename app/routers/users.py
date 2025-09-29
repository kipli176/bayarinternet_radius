# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy import text

from app.utils import coa
from app.utils.wa_gateway import send_whatsapp, format_user_created, format_user_activated
from app.database import get_db
from app import models
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.routers.resellers import get_current_reseller

router = APIRouter()

# ➕ tambah PPP user
@router.post("", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    existing = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.username == payload.username
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = models.user.PPPUser(
        reseller_id=reseller.id,
        profile_id=payload.profile_id,
        username=payload.username,
        password_hash=payload.password,  # hash di schema validator
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        alamat=payload.alamat,   # ✅ tambahkan alamat
        status="active",
        active_until=payload.active_until,
        is_active=True
    )

    db.add(user)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)}) 
    db.commit()
    db.refresh(user)

    # cari profile info
    profile = db.query(models.profile.PPPProfile).filter(models.profile.PPPProfile.id == user.profile_id).first()

    msg = format_user_created(user, profile)
    if user.phone:
        send_whatsapp(user.phone, msg) 

    return user

# 📋 daftar PPP user
@router.get("", response_model=List[UserResponse])
def list_users(
    status: Optional[str] = Query(None, description="active/suspended/expired"),
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    q = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.deleted_at.is_(None)
    )
    if status:
        q = q.filter(models.user.PPPUser.status == status)
    return q.all()

# 🔎 detail user
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == user_id,
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.deleted_at.is_(None)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ✏️ update PPP user
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == user_id,
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.deleted_at.is_(None)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # simpan status lama
    old_status = user.status

    # update fields
    for key, value in payload.dict(exclude_unset=True).items():
        if key == "password":
            setattr(user, "password_hash", value)
        else:
            setattr(user, key, value)

    # audit trigger
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(user)

    # jika status diubah dan berbeda dengan status lama, disconnect
    if payload.status and payload.status != old_status:
        routers = db.query(models.router.MikrotikRouter).filter(
            models.router.MikrotikRouter.reseller_id == reseller.id
        ).all()
        for r in routers:
            try:
                result = coa.disconnect_user(
                    username=user.username,
                    nas_ip=str(r.mgmt_ip),
                    secret=r.radius_secret
                )
                print(f"Disconnect {user.username} @ {r.mgmt_ip}: {result}")
            except Exception as e:
                print(f"Failed disconnect {user.username} @ {r.mgmt_ip}: {e}")

        # ➕ kirim WA jika status aktif
        if payload.status == "active":
            try:
                if user.phone:  # pastikan ada nomor WA
                    msg = format_user_activated(user)
                    if user.phone:
                        send_whatsapp(user.phone, msg)
            except Exception as e:
                print(f"Gagal kirim WhatsApp ke {user.username}: {e}")
    return user

# ❌ hapus user (soft delete)
@router.delete("/{user_id}", response_model=UserResponse)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == user_id,
        models.user.PPPUser.reseller_id == reseller.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Putuskan koneksi user dari semua router (CoA)
    routers = db.query(models.router.MikrotikRouter).filter(
        models.router.MikrotikRouter.reseller_id == reseller.id
    ).all()
    for r in routers:
        try:
            result = coa.disconnect_user(
                username=user.username,
                nas_ip=str(r.mgmt_ip),
                secret=r.radius_secret
            )
            print(f"Disconnect {user.username} @ {r.mgmt_ip}: {result}")
        except Exception as e:
            print(f"Failed disconnect {user.username} @ {r.mgmt_ip}: {e}")

    # Ambil snapshot user untuk response sebelum dihapus
    response_user = UserResponse.from_orm(user)

    # Hapus user permanen
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.delete(user)
    db.commit()

    return response_user

