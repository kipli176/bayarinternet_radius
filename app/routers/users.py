# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy import text

from app.utils import coa, wa_gateway
from app.database import get_db
from app import models
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.routers.resellers import get_current_reseller

router = APIRouter()

# ➕ tambah PPP user
@router.post("/", response_model=UserResponse)
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

    # buat pesan WA
    msg = (
        f"Halo {user.full_name or user.username},\n"
        f"Akun internet Anda berhasil dibuat 🎉\n\n"
        f"🔑 Username : {user.username}\n"
        f"📡 Paket    : {profile.name if profile else '-'} "
        f"({profile.burst_limit_up}/{profile.burst_limit_down})\n"
        f"📅 Aktif sampai : {user.active_until.strftime('%d-%m-%Y') if user.active_until else '-'}\n\n"
        f"Silakan tunggu teknisi datang.\n"
        f"Terima kasih sudah menggunakan layanan kami 🙏"
    )

    if user.phone:
        wa_gateway.send_whatsapp(user.phone, msg)

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

    # jika status diubah jadi suspended/disable → coba disconnect di semua router reseller
    if payload.status and payload.status.lower() in ["suspended", "disabled"]:
        routers = db.query(models.router.MikrotikRouter).filter(
            models.router.MikrotikRouter.reseller_id == reseller.id
        ).all()
        print(routers)
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

    return user

# ❌ hapus user (soft delete)
@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == user_id,
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.deleted_at.is_(None)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.deleted_at = datetime.utcnow()
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)}) 
    db.commit()
    for router in db.query(models.router.MikrotikRouter).filter(models.router.MikrotikRouter.reseller_id == reseller.id).all():
        try:
            result = coa.disconnect_user(
                username=user.username,
                nas_ip=str(router.mgmt_ip),
                secret=router.radius_secret
            )
            print(f"Disconnect {user.username} @ {router.mgmt_ip}: {result}")
        except Exception as e:
            print(f"Failed disconnect {user.username} @ {router.mgmt_ip}: {e}")
 
    return {"status": "success", "message": "User deleted"}
