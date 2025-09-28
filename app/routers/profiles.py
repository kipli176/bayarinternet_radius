# app/routers/profiles.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from sqlalchemy import text

from app.database import get_db
from app import models
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse
from app.routers.resellers import get_current_reseller

router = APIRouter()

# ➕ tambah profil PPP
@router.post("/", response_model=ProfileResponse)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    profile = models.profile.PPPProfile(
        reseller_id=reseller.id,
        name=payload.name,
        group_name=payload.group_name,
        price=payload.price,
        rate_limit_up=payload.rate_limit_up,
        rate_limit_down=payload.rate_limit_down,
        burst_limit_up=payload.burst_limit_up,
        burst_limit_down=payload.burst_limit_down,
        burst_threshold_up=payload.burst_threshold_up,
        burst_threshold_down=payload.burst_threshold_down,
        burst_time_up=payload.burst_time_up,
        burst_time_down=payload.burst_time_down,
        priority=payload.priority,
        auto_pool=payload.auto_pool,
        is_active=True
    )
    db.add(profile)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(profile)
    return profile

# 📋 daftar semua profil reseller
@router.get("/", response_model=List[ProfileResponse])
def list_profiles(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.reseller_id == reseller.id,
        models.profile.PPPProfile.deleted_at.is_(None)
    ).all()

# 🔎 detail profil
@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    profile = db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.id == profile_id,
        models.profile.PPPProfile.reseller_id == reseller.id,
        models.profile.PPPProfile.deleted_at.is_(None)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

# ✏️ update profil
@router.patch("/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: str, payload: ProfileUpdate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    profile = db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.id == profile_id,
        models.profile.PPPProfile.reseller_id == reseller.id,
        models.profile.PPPProfile.deleted_at.is_(None)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(profile, key, value)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(profile)
    return profile

# ❌ hapus (soft delete) profil
@router.delete("/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    profile = db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.id == profile_id,
        models.profile.PPPProfile.reseller_id == reseller.id,
        models.profile.PPPProfile.deleted_at.is_(None)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.deleted_at = datetime.utcnow()
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    return {"status": "success", "message": "Profile deleted"}
