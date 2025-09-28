# app/routers/customer_invoices.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import text
from app.utils.wa_gateway import send_whatsapp, format_invoice_paid_message
from app.utils.time import add_months_keep_dom  # helper untuk tambah bulan

from app.database import get_db
from app import models
from app.schemas.customer_invoice import (
    CustomerInvoiceCreate,
    CustomerInvoiceUpdate,
    CustomerInvoiceResponse
)
from app.routers.resellers import get_current_reseller

router = APIRouter()

# ➕ buat customer invoice
@router.post("/", response_model=CustomerInvoiceResponse)
def create_customer_invoice(payload: CustomerInvoiceCreate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    # pastikan user milik reseller
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == payload.user_id,
        models.user.PPPUser.reseller_id == reseller.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ambil profil untuk harga default
    profile = db.query(models.profile.PPPProfile).filter(models.profile.PPPProfile.id == payload.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    amount = payload.amount or float(profile.price)

    invoice = models.customer_invoice.CustomerInvoice(
        reseller_id=reseller.id,
        user_id=user.id,
        profile_id=profile.id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        amount=amount,
        status="draft"
    )
    db.add(invoice)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)}) 
    db.commit()
    db.refresh(invoice)
    return invoice

# 📋 daftar invoice customer milik reseller
@router.get("", response_model=List[CustomerInvoiceResponse])
def list_customer_invoices(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id
    ).order_by(models.customer_invoice.CustomerInvoice.created_at.desc()).all()

# 🔎 detail invoice customer
@router.get("/{invoice_id}", response_model=CustomerInvoiceResponse)
def get_customer_invoice(invoice_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    invoice = db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.id == invoice_id,
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Customer invoice not found")
    return invoice
# ✏️ update status invoice customer 

@router.patch("/{invoice_id}", response_model=CustomerInvoiceResponse)
def update_customer_invoice(
    invoice_id: str,
    payload: CustomerInvoiceUpdate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller)
):
    invoice = db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.id == invoice_id,
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Customer invoice not found")

    
    # update status
    if payload.status:
        invoice.status = payload.status

        # kalau invoice dibayar → catat paid_at
        if payload.status == "paid" and not invoice.paid_at:
            invoice.paid_at = datetime.now()

    db.execute(
        text("SELECT set_config('app.current_user', :uid, true)"),
        {"uid": str(reseller.id)}
    )
    db.commit()
    db.refresh(invoice)

    # jika status berubah jadi paid → extend active_until user
    if invoice.status == "paid":
        user = db.query(models.user.PPPUser).filter(
            models.user.PPPUser.id == invoice.user_id
        ).first()
        profile = db.query(models.profile.PPPProfile).filter(
            models.profile.PPPProfile.id == invoice.profile_id
        ).first()

        if user and profile:
            # hitung jumlah bulan dibayar dari amount
            months_paid = max(1, round(invoice.amount / float(profile.price or 1)))

            if user.active_until and user.active_until > datetime.utcnow():
                # extend dari active_until lama
                user.active_until = add_months_keep_dom(user.active_until, months_paid)
            else:
                # fallback → mulai dari sekarang
                base = invoice.period_end or datetime.utcnow()
                user.active_until = add_months_keep_dom(base, months_paid)

            # jika sebelumnya suspended → aktifkan kembali
            if user.status == "suspended":
                user.status = "active"

            db.execute(
                text("SELECT set_config('app.current_user', :uid, true)"),
                {"uid": str(reseller.id)}
            )
            db.commit()
            db.refresh(user)

            # kirim WA konfirmasi pembayaran
            if user.phone:
                msg = format_invoice_paid_message(
                    invoice, is_customer=True, user=user, profile=profile
                )
                send_whatsapp(user.phone, msg)

    return invoice