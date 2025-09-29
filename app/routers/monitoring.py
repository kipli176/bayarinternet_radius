from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models
from app.schemas.monitoring import SessionResponse
from app.routers.resellers import get_current_reseller
from app.utils.responses import success_response, error_response

router = APIRouter()

# 📋 daftar session aktif
@router.get("", response_model=List[SessionResponse])
def list_active_sessions(
    db: Session = Depends(get_db), reseller=Depends(get_current_reseller)
):
    sessions = (
        db.query(models.radacct.RadAcct)
        .join(models.user.PPPUser, models.radacct.RadAcct.username == models.user.PPPUser.username)
        .filter(
            models.radacct.RadAcct.acctstoptime.is_(None),
            models.user.PPPUser.reseller_id == reseller.id,
        )
        .all()
    )
    return success_response(sessions, "Active sessions retrieved successfully")


# 🔎 detail session user
@router.get("/{username}", response_model=List[SessionResponse])
def get_user_sessions(
    username: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)
):
    user = (
        db.query(models.user.PPPUser)
        .filter(
            models.user.PPPUser.username == username,
            models.user.PPPUser.reseller_id == reseller.id,
        )
        .first()
    )
    if not user:
        return error_response("User not found", 404)

    sessions = (
        db.query(models.radacct.RadAcct)
        .filter(
            models.radacct.RadAcct.username == username,
            models.radacct.RadAcct.acctstoptime.is_(None),
        )
        .all()
    )
    return success_response(sessions, "User sessions retrieved successfully")


# ❌ disconnect user manual
@router.delete("/{username}")
def disconnect_user(
    username: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)
):
    user = (
        db.query(models.user.PPPUser)
        .filter(
            models.user.PPPUser.username == username,
            models.user.PPPUser.reseller_id == reseller.id,
        )
        .first()
    )
    if not user:
        return error_response("User not found", 404)

    # opsional: trigger CoA
    # coa.disconnect_user(username=username, nas_ip="...", secret="...")

    return success_response({"detail": f"Disconnect request sent for {username}"})
