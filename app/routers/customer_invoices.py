# app/routers/customer_invoices.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import text
from app.utils.wa_gateway import send_whatsapp, format_invoice_paid_message
from app.utils.time import add_months_keep_dom  # helper untuk tambah bulan
from app.utils.responses import success_response, error_response

from app.database import get_db
from app import models
from app.schemas.customer_invoice import (
    CustomerInvoiceCreate,
    CustomerInvoiceUpdate,
    CustomerInvoiceResponse
)
from app.routers.resellers import get_current_reseller
from decimal import Decimal, ROUND_HALF_UP
from app.utils import coa  # CoA untuk disconnect user
import logging
logger = logging.getLogger("app.routers.customer_invoices")

router = APIRouter()

# ➕ buat customer invoice
@router.post("", response_model=CustomerInvoiceResponse)
def create_customer_invoice(
    payload: CustomerInvoiceCreate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller),
):
    # pastikan user ada & milik reseller
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == payload.user_id,
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.deleted_at.is_(None)
    ).first()
    if not user:
        return error_response("User not found", 404)

    # ambil profil langsung dari user
    if not user.profile_id:
        return error_response("User does not have an assigned profile", 400)

    profile = db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.id == user.profile_id
    ).first()
    if not profile:
        return error_response("Profile not found", 404)

    # jika amount tidak diberikan, gunakan harga profil
    amount = payload.amount or profile.price

    invoice = models.customer_invoice.CustomerInvoice(
        reseller_id=reseller.id,
        user_id=user.id,
        profile_id=user.profile_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        amount=amount,
        status="draft"   # default saat create
    )

    db.add(invoice)
    db.execute(
        text("SELECT set_config('app.current_user', :uid, true)"),
        {"uid": str(reseller.id)}
    )
    db.commit()
    db.refresh(invoice)

    return success_response(
        CustomerInvoiceResponse.from_orm(invoice),
        "Customer invoice created successfully",
        201
    )

# 📋 daftar invoice customer milik reseller
@router.get("", response_model=List[CustomerInvoiceResponse])
def list_customer_invoices(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return success_response(db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id
    ).order_by(models.customer_invoice.CustomerInvoice.created_at.desc()).all(), "Customer invoices retrieved successfully")

# 🔎 detail invoice customer
@router.get("/{invoice_id}", response_model=CustomerInvoiceResponse)
def get_customer_invoice(invoice_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    invoice = db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.id == invoice_id,
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id
    ).first()
    if not invoice:
        return error_response("Customer invoice not found", 404)
    return success_response(invoice, "Customer invoice retrieved successfully")

# ✏️ update status invoice customer
@router.patch("/{invoice_id}", response_model=CustomerInvoiceResponse)
def update_customer_invoice(
    invoice_id: str,
    payload: CustomerInvoiceUpdate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller),
):
    invoice = db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.id == invoice_id,
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id,
    ).first()
    if not invoice:
        return error_response("Customer invoice not found", 404)

    # update status invoice
    if payload.status:
        invoice.status = payload.status
        if payload.status == "paid" and not invoice.paid_at:
            invoice.paid_at = datetime.utcnow()

    db.execute(
        text("SELECT set_config('app.current_user', :uid, true)"),
        {"uid": str(reseller.id)},
    )
    db.commit()
    db.refresh(invoice)

    # jika invoice dibayar
    if invoice.status == "paid":
        user = db.query(models.user.PPPUser).filter(
            models.user.PPPUser.id == invoice.user_id
        ).first()
        profile = db.query(models.profile.PPPProfile).filter(
            models.profile.PPPProfile.id == invoice.profile_id
        ).first()

        if user and profile:
            # 1) disconnect dulu semua sesi user di NAS reseller
            routers = db.query(models.router.MikrotikRouter).filter(
                models.router.MikrotikRouter.reseller_id == reseller.id,
                models.router.MikrotikRouter.deleted_at.is_(None),
                models.router.MikrotikRouter.is_active.is_(True),
            ).all()
            for r in routers:
                try:
                    coa.disconnect_user(
                        username=user.username,
                        nas_ip=str(r.mgmt_ip),
                        secret=r.radius_secret,
                    )
                except Exception as e:
                    logger.warning(
                        f"[update_customer_invoice] CoA disconnect gagal {user.username} @ {r.mgmt_ip}: {e}"
                    )

            # 2) hitung jumlah bulan dibayar
            months_paid = max(1, round(invoice.amount / float(profile.price or 1)))

            # 3) extend active_until (logika lama dipertahankan)
            if user.active_until and user.active_until > datetime.utcnow():
                user.active_until = add_months_keep_dom(user.active_until, months_paid)
            else:
                base = invoice.period_end or datetime.utcnow()
                user.active_until = add_months_keep_dom(base, months_paid)

            # 4) kalau status suspended → aktifkan kembali
            if user.status == "suspended":
                user.status = "active"

            db.execute(
                text("SELECT set_config('app.current_user', :uid, true)"),
                {"uid": str(reseller.id)},
            )
            db.commit()
            db.refresh(user)

            # 5) kirim WA konfirmasi pembayaran
            if user.phone:
                try:
                    msg = format_invoice_paid_message(
                        invoice, is_customer=True, user=user, profile=profile
                    )
                    send_whatsapp(user.phone, msg)
                except Exception as e:
                    logger.error(
                        f"[update_customer_invoice] WA notif gagal ke {user.username}: {e}"
                    )

    return success_response(
        CustomerInvoiceResponse.from_orm(invoice),
        "Customer invoice updated successfully",
    )
