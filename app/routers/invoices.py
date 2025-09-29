
# app/routers/invoices.py (potongan revisi)
from decimal import Decimal, ROUND_HALF_UP
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from sqlalchemy import text

from app.database import get_db
from app import models
from app.schemas.invoice import (
    InvoiceResponse,
    InvoiceCreate,
    InvoiceUpdate
)
from app.routers.resellers import get_current_reseller
from app.utils.responses import success_response, error_response
from app.utils.wa_gateway import send_whatsapp, format_invoice_paid_message, format_invoice_generated_reseller

router = APIRouter()

# 📋 daftar invoice reseller
@router.get("", response_model=List[InvoiceResponse])
def list_invoices(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return success_response(db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.reseller_id == reseller.id
    ).order_by(models.invoice.Invoice.created_at.desc()).all(), "Invoices retrieved successfully")

# ➕ generate invoice reseller

@router.post("/generate", response_model=InvoiceResponse)
def generate_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller),
):
    # 1) Cek duplikasi periode
    existing = db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.reseller_id == reseller.id,
        models.invoice.Invoice.period_start == payload.period_start,
        models.invoice.Invoice.period_end == payload.period_end
    ).first()
    if existing:
        return error_response("Invoice for this period already exists", 409)

    # 2) Hitung jumlah user aktif
    users_count = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.status == "active"
    ).count()

    # 3) Hitung harga & subtotal
    unit_price = Decimal(str(reseller.price_per_user or 0))
    subtotal = (Decimal(users_count) * unit_price).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    # 4) Volume pricing (diskon jika ada)
    discount = Decimal("0.00")
    vp = reseller.volume_pricing or {}
    try:
        tiers = {int(k): Decimal(str(v)) for k, v in vp.items()} if isinstance(vp, dict) else {}
        applicable = max([k for k in tiers.keys() if users_count >= k], default=None)
        if applicable is not None:
            rate = tiers[applicable]
            discount = (subtotal * rate).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
    except Exception:
        discount = Decimal("0.00")

    # 5) Pajak (10%)
    tax = ((subtotal - discount) * Decimal("0.10")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    # 6) Total
    total = (subtotal - discount + tax).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    # 7) Snapshot meta
    meta = {
        "company_name": reseller.company_name,
        "alamat": reseller.alamat,
        "logo": reseller.logo,
        "price_per_user": float(unit_price),
        "currency": reseller.currency,
        "users_count": users_count,
        "volume_pricing": reseller.volume_pricing,
    }

    # 8) Buat invoice baru
    invoice = models.invoice.Invoice(
        reseller_id=reseller.id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        users_count=users_count,
        unit_price=unit_price,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=total,
        currency=reseller.currency or "IDR",
        status="unpaid",   # 🔑 langsung unpaid
        meta=meta
    )

    db.add(invoice)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(invoice)

    # 9) Kirim WA ke reseller
    if reseller.phone:
        try:
            msg = format_invoice_generated_reseller(reseller, invoice)
            send_whatsapp(reseller.phone, msg)
        except Exception as e:
            print(f"[generate_invoice] Gagal kirim WA: {e}")

    return success_response(InvoiceResponse.from_orm(invoice), "Invoice created successfully", 201)



# 🔎 detail invoice reseller
@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    invoice = db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.id == invoice_id,
        models.invoice.Invoice.reseller_id == reseller.id
    ).first()
    if not invoice:
        return error_response("Invoice not found", 404)
    return success_response(InvoiceResponse.from_orm(invoice), "Invoice retrieved successfully")


# ✏️ update status invoice reseller
@router.patch("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(invoice_id: str, payload: InvoiceUpdate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    invoice = db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.id == invoice_id,
        models.invoice.Invoice.reseller_id == reseller.id
    ).first()
    if not invoice:
        return error_response("Invoice not found", 404)

    if payload.status:
        invoice.status = payload.status

    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)}) 
    db.commit()
    db.refresh(invoice)
    # kirim WA jika paid
    if invoice.status == "paid" and reseller.phone:
        msg = format_invoice_paid_message(invoice, is_customer=False, user=reseller)
        send_whatsapp(reseller.phone, msg)
    return success_response(InvoiceResponse.from_orm(invoice), "Invoice updated successfully")
