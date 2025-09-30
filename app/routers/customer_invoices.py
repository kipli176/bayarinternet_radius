# app/routers/customer_invoices.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import text
from app.utils.wa_gateway import format_invoice_rollback_message, send_whatsapp, format_invoice_paid_message, format_invoice_unpaid_message, format_invoice_rollback_message
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
    period_end = datetime.combine(add_months_keep_dom(base_date, months), datetime.min.time())

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

        if user and profile:
            old_status = user.status

            # extend masa aktif ke akhir periode invoice
            user.active_until = invoice.period_end.date()
            if user.status == "suspended":
                user.status = "active"

            db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
            db.commit()
            db.refresh(user)

            # 🔌 disconnect supaya session lama terputus
            if user.status != old_status:
                routers = db.query(models.router.MikrotikRouter).filter(
                    models.router.MikrotikRouter.reseller_id == reseller.id,
                    models.router.MikrotikRouter.deleted_at.is_(None),
                    models.router.MikrotikRouter.is_active.is_(True),
                ).all()
                for r in routers:
                    try:
                        result = coa.disconnect_user(
                            username=user.username,
                            nas_ip=str(r.mgmt_ip),
                            secret=r.radius_secret,
                        )
                        print(f"Disconnect {user.username} @ {r.mgmt_ip}: {result}")
                    except Exception as e:
                        print(f"Failed disconnect {user.username} @ {r.mgmt_ip}: {e}")

            # 📲 kirim WA konfirmasi pembayaran
            if user.phone:
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
            old_status = user.status

            # kembalikan masa aktif ke sebelum invoice ini berlaku
            rollback_date = (invoice.period_start - timedelta(days=1)).date()
            user.active_until = rollback_date
            user.status = "suspended"

            db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
            db.commit()
            db.refresh(user)

            # 🔌 disconnect supaya user langsung terputus
            if user.status != old_status:
                routers = db.query(models.router.MikrotikRouter).filter(
                    models.router.MikrotikRouter.reseller_id == reseller.id,
                    models.router.MikrotikRouter.deleted_at.is_(None),
                    models.router.MikrotikRouter.is_active.is_(True),
                ).all()
                for r in routers:
                    try:
                        result = coa.disconnect_user(
                            username=user.username,
                            nas_ip=str(r.mgmt_ip),
                            secret=r.radius_secret,
                        )
                        print(f"Rollback disconnect {user.username} @ {r.mgmt_ip}: {result}")
                    except Exception as e:
                        print(f"Rollback failed disconnect {user.username} @ {r.mgmt_ip}: {e}")

            # 📲 kirim WA info rollback
            if user.phone:
                try:
                    msg = format_invoice_rollback_message(invoice, user=user)
                    send_whatsapp(user.phone, msg)
                except Exception as e:
                    logger.error(f"[update_customer_invoice] WA rollback gagal ke {user.username}: {e}")

    # audit & simpan perubahan invoice
    db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
    db.commit()
    db.refresh(invoice)

    return success_response(
        CustomerInvoiceResponse.from_orm(invoice),
        "Customer invoice updated successfully",
    )
