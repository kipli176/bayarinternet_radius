# app/routers/customer_invoices.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import text
from app.utils.wa_gateway import send_whatsapp, format_invoice_paid_message, format_invoice_unpaid_message
from app.utils.time import add_months_keep_dom  # helper untuk tambah bulan
from app.utils.responses import success_response, error_response

from app.database import get_db
from app import models
from app.schemas.customer_invoice import ( CustomerInvoiceCreate, CustomerInvoiceUpdate, CustomerInvoiceResponse)
from app.routers.resellers import get_current_reseller
from decimal import Decimal, ROUND_HALF_UP
from app.utils import coa  # CoA untuk disconnect user
import logging
logger = logging.getLogger("app.routers.customer_invoices")

router = APIRouter()

def _add_months_keep_dom(base_date, months: int):
    """Tambah bulan mempertahankan day-of-month. Clamp ke akhir bulan kalau DOM tidak ada."""
    from calendar import monthrange
    y, m = base_date.year, base_date.month
    m += months
    y += (m - 1) // 12
    m = ((m - 1) % 12) + 1
    day = min(base_date.day, monthrange(y, m)[1])
    return base_date.replace(year=y, month=m, day=day)

# ➕ buat customer invoice
# Default (1 bulan):

# {
#   "user_id": "9c88d6e4-bbbc-4e2e-84db-3dfd1e56d3a0"
# }


# Bayar 3 bulan sekaligus:

# {
#   "user_id": "9c88d6e4-bbbc-4e2e-84db-3dfd1e56d3a0",
#   "months": 3
# }


# Dengan catatan khusus (meta override):

# {
#   "user_id": "9c88d6e4-bbbc-4e2e-84db-3dfd1e56d3a0",
#   "months": 2,
#   "meta": { "catatan": "Bayar langsung 2 bulan" }
# }

@router.post("", response_model=CustomerInvoiceResponse)
def create_customer_invoice(
    payload: CustomerInvoiceCreate,
    db: Session = Depends(get_db),
    reseller=Depends(get_current_reseller),
):
    # validasi user
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == payload.user_id,
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.deleted_at.is_(None)
    ).first()
    if not user:
        return error_response("User not found", 404)
    if not user.profile_id:
        return error_response("User does not have an assigned profile", 400)

    profile = db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.id == user.profile_id
    ).first()
    if not profile:
        return error_response("Profile not found", 404)

    months = max(1, int(payload.months or 1))

    # ✳️ Periode berdasarkan active_until
    if user.active_until:
        base_date = user.active_until
    else:
        base_date = datetime.utcnow().date()

    period_start = datetime.combine(base_date, datetime.min.time())
    period_end = datetime.combine(_add_months_keep_dom(base_date, months), datetime.min.time())

    # cek duplikat invoice
    existing = db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.user_id == user.id,
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id,
        models.customer_invoice.CustomerInvoice.period_start == period_start,
        models.customer_invoice.CustomerInvoice.period_end == period_end,
    ).first()
    if existing:
        return error_response("Invoice for this period already exists", 409)

    # hitung nominal
    amount = Decimal(profile.price or 0) * months

    meta = (payload.meta or {}) | {
        "user_name": user.full_name or user.username,
        "profile_name": profile.name,
        "price_per_month": float(profile.price or 0),
        "months": months,
        "subtotal": float(amount),
        "currency": reseller.currency or "IDR",
    }

    invoice = models.customer_invoice.CustomerInvoice(
        reseller_id=reseller.id,
        user_id=user.id,
        profile_id=user.profile_id,
        period_start=period_start,
        period_end=period_end,
        amount=amount,
        status="unpaid",
        meta=meta,
    )

    db.add(invoice)
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(invoice)

    if user.phone:
        try:
            msg = format_invoice_unpaid_message(invoice, user=user, profile=profile)
            send_whatsapp(user.phone, msg)
        except Exception as e:
            logger.error(f"[create_customer_invoice] WA gagal ke {user.username}: {e}")

    return success_response(CustomerInvoiceResponse.from_orm(invoice), "Customer invoice created successfully", 201)

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

    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == invoice.user_id
    ).first()
    profile = db.query(models.profile.PPPProfile).filter(
        models.profile.PPPProfile.id == invoice.profile_id
    ).first()

    # ============== jika status -> PAID ==============
    if payload.status and payload.status.lower() == "paid":
        if invoice.status == "paid":
            return error_response("Invoice already paid", 400)

        invoice.status = "paid"
        invoice.paid_at = datetime.utcnow()

        if user:
            old_status = user.status

            # extend masa aktif ke invoice.period_end
            user.active_until = invoice.period_end.date()

            # aktifkan kembali jika suspended
            if user.status == "suspended":
                user.status = "active"

            db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
            db.commit()
            db.refresh(user)

            # disconnect session lama
            if user.status != old_status:
                routers = db.query(models.router.MikrotikRouter).filter(
                    models.router.MikrotikRouter.reseller_id == reseller.id,
                    models.router.MikrotikRouter.deleted_at.is_(None),
                    models.router.MikrotikRouter.is_active.is_(True),
                ).all()
                for r in routers:
                    try:
                        coa.disconnect_user(user.username, str(r.mgmt_ip), r.radius_secret)
                    except Exception as e:
                        print(f"Disconnect failed {user.username} @ {r.mgmt_ip}: {e}")

            # kirim WA konfirmasi pembayaran
            if user.phone and profile:
                try:
                    msg = format_invoice_paid_message(invoice, user=user, profile=profile)
                    send_whatsapp(user.phone, msg)
                except Exception as e:
                    logger.error(f"[update_customer_invoice] WA gagal ke {user.username}: {e}")

    # ============== jika status -> UNPAID (rollback) ==============
    elif payload.status and payload.status.lower() == "unpaid":
        if invoice.status != "paid":
            return error_response("Only paid invoices can be rolled back to unpaid", 400)

        invoice.status = "unpaid"
        invoice.paid_at = None

        if user:
            # kembalikan active_until ke sebelum invoice berlaku
            rollback_date = (invoice.period_start - timedelta(days=1)).date()
            user.active_until = rollback_date

            # suspend user lagi
            user.status = "suspended"

            db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
            db.commit()
            db.refresh(user)

            # kirim WA info rollback (opsional)
            if user.phone:
                try:
                    msg = (
                        f"Halo {user.full_name or user.username},\n"
                        f"⚠️ Pembayaran pada invoice {invoice.id} telah dibatalkan.\n\n"
                        f"Layanan Anda kembali dalam status *SUSPEND*.\n"
                        f"Silakan hubungi admin jika ada kesalahan.\n"
                    )
                    send_whatsapp(user.phone, msg)
                except Exception as e:
                    logger.error(f"[update_customer_invoice] WA rollback gagal ke {user.username}: {e}")

    # audit & simpan
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(invoice)

    return success_response(
        CustomerInvoiceResponse.from_orm(invoice),
        "Customer invoice updated successfully",
    )
