# app/routers/invoices.py
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from sqlalchemy import text
from app.utils.wa_gateway import send_whatsapp, format_invoice_paid_message

from app.database import get_db
from app import models
from app.schemas.invoice import (
    InvoiceResponse,
    InvoiceCreate,
    InvoiceUpdate
)
from app.routers.resellers import get_current_reseller
from app.utils.responses import success_response, error_response

router = APIRouter()

# 📋 daftar invoice reseller
@router.get("", response_model=List[InvoiceResponse])
def list_invoices(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    return success_response(db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.reseller_id == reseller.id
    ).order_by(models.invoice.Invoice.created_at.desc()).all(), "Invoices retrieved successfully")

# ➕ generate invoice reseller
@router.post("/generate", response_model=InvoiceResponse)
def generate_invoice(payload: InvoiceCreate, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    # hitung jumlah user aktif reseller
    users_count = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.status == "active"
    ).count()

    unit_price = reseller.price_per_user or 0
    subtotal = users_count * unit_price
    discount = 0
    tax = subtotal * Decimal('0.1')  # contoh PPN 10%
    total = subtotal - discount + tax

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
        currency="IDR",
        status="draft"
    )
    db.add(invoice)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)}) 
    db.commit()
    db.refresh(invoice)
    return success_response(invoice, "Invoice created successfully", 201)

# 🔎 detail invoice reseller
@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    invoice = db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.id == invoice_id,
        models.invoice.Invoice.reseller_id == reseller.id
    ).first()
    if not invoice:
        return error_response("Invoice not found", 404)
    return success_response(invoice, "Invoice retrieved successfully")

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
    return success_response(invoice, "Invoice updated successfully")
