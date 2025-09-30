# worker/jobs/customer_billing.py
from datetime import datetime, date, timedelta
from calendar import monthrange
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.sql import text

from app.database import SessionLocal
from app import models
from app.utils.wa_gateway import send_whatsapp, format_invoice_unpaid_message 
from app.utils import coa

import logging
logger = logging.getLogger(__name__)


def _add_months_keep_dom(d: date, months: int) -> date:
    """Tambah N bulan ke tanggal (pertahankan day-of-month; jika tidak ada, clamp ke akhir bulan)."""
    y, m = d.year, d.month
    m += months
    y += (m - 1) // 12
    m = ((m - 1) % 12) + 1
    last_day = monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


# 1) H-3 sebelum active_until: generate invoice UNPAID
def generate_customer_invoices_h_minus_3():
    """
    Untuk setiap user ACTIVE yang punya active_until,
    jika today == active_until - 3 hari -> generate invoice 1 bulan:
      period_start = active_until (00:00)
      period_end   = active_until + 1 bulan (00:00)
      status       = unpaid
      WA terkirim ke customer
    """
    db: Session = SessionLocal()
    try:
        today = date.today()

        users = db.query(models.user.PPPUser).filter(
            models.user.PPPUser.status == "active",
            models.user.PPPUser.deleted_at.is_(None),
            models.user.PPPUser.active_until.isnot(None)
        ).all()

        created = 0
        for user in users:
            # H-3 dari active_until
            if user.active_until and (user.active_until - timedelta(days=3) == today):
                # hitung periode (patokan active_until, bukan awal bulan)
                start_d = user.active_until
                end_d = _add_months_keep_dom(user.active_until, 1)

                period_start = datetime.combine(start_d, datetime.min.time())
                period_end   = datetime.combine(end_d,   datetime.min.time())

                # cegah duplikat exact periode
                exists = db.query(models.customer_invoice.CustomerInvoice).filter(
                    models.customer_invoice.CustomerInvoice.user_id == user.id,
                    models.customer_invoice.CustomerInvoice.reseller_id == user.reseller_id,
                    models.customer_invoice.CustomerInvoice.period_start == period_start,
                    models.customer_invoice.CustomerInvoice.period_end == period_end,
                ).first()
                if exists:
                    continue

                # ambil profil & harga
                profile = db.query(models.profile.PPPProfile).filter(
                    models.profile.PPPProfile.id == user.profile_id
                ).first()
                if not profile:
                    logger.warning(f"[H-3] Skip {user.username}: profile not found")
                    continue

                amount = Decimal(profile.price or 0)

                inv = models.customer_invoice.CustomerInvoice(
                    reseller_id=user.reseller_id,
                    user_id=user.id,
                    profile_id=user.profile_id,
                    period_start=period_start,
                    period_end=period_end,
                    amount=amount,
                    status="unpaid",
                    meta={
                        "user_name": user.full_name or user.username,
                        "profile_name": profile.name,
                        "price_per_month": float(profile.price or 0),
                        "months": 1,
                        "subtotal": float(amount),
                        "currency": "IDR",
                        "period_start_str": period_start.strftime("%d-%m-%Y"),
                        "period_end_str":   period_end.strftime("%d-%m-%Y"),
                    }
                )
                db.add(inv)
                # audit trigger (jika dipakai)
                db.execute(text("SELECT set_config('app.current_user', :uid, true)"),
                           {"uid": str(user.reseller_id)})
                db.commit()
                db.refresh(inv)
                created += 1

                # kirim WA tagihan
                if user.phone:
                    try:
                        send_whatsapp(user.phone, format_invoice_unpaid_message(inv, user=user, profile=profile))
                    except Exception as e:
                        logger.error(f"[H-3] WA gagal {user.username}: {e}")

        logger.info(f"[H-3] generate_customer_invoices_h_minus_3: created={created}")

    except Exception as e:
        logger.exception(f"[H-3] ERROR: {e}")
        db.rollback()
    finally:
        db.close()


# 2) H-5 sebelum AKHIR BULAN: reminder unpaid
def remind_unpaid_h_minus_5_eom():
    """
    Jika today == (last_day_of_month - 5), kirim WA reminder
    ke semua invoice UNPAID yang period_end jatuh pada bulan ini.
    """
    db: Session = SessionLocal()
    try:
        today = date.today()
        # hitung first/last day bulan ini
        first_day = today.replace(day=1)
        last_day  = date(today.year, today.month, monthrange(today.year, today.month)[1])

        if today != (last_day - timedelta(days=5)):
            return  # bukan H-5, skip

        invoices = db.query(models.customer_invoice.CustomerInvoice).filter(
            models.customer_invoice.CustomerInvoice.status == "unpaid",
            models.customer_invoice.CustomerInvoice.paid_at.is_(None),
            models.customer_invoice.CustomerInvoice.period_end >= datetime.combine(first_day, datetime.min.time()),
            models.customer_invoice.CustomerInvoice.period_end <= datetime.combine(last_day,  datetime.min.time()),
        ).all()

        sent = 0
        for inv in invoices:
            user = db.query(models.user.PPPUser).filter(
                models.user.PPPUser.id == inv.user_id
            ).first()
            profile = db.query(models.profile.PPPProfile).filter(
                models.profile.PPPProfile.id == inv.profile_id
            ).first()
            if not user or not user.phone:
                continue
            try:
                send_whatsapp(user.phone, format_invoice_unpaid_message(inv, user=user, profile=profile))
                sent += 1
            except Exception as e:
                logger.error(f"[H-5 EOM] WA gagal {user.username}: {e}")

        logger.info(f"[H-5 EOM] reminder sent={sent}")

    except Exception as e:
        logger.exception(f"[H-5 EOM] ERROR: {e}")
        db.rollback()
    finally:
        db.close()


# 3) Tanggal 1 bulan berikutnya: suspend semua yang masih UNPAID
def suspend_unpaid_on_first():
    """
    Jika hari ini tanggal 1, suspend semua user yang masih memiliki invoice UNPAID
    dengan period_end < today (berarti sudah lewat jatuh tempo), lalu CoA disconnect + WA.
    """
    db: Session = SessionLocal()
    try:
        today = date.today()
        if today.day != 1:
            return

        invoices = db.query(models.customer_invoice.CustomerInvoice).filter(
            models.customer_invoice.CustomerInvoice.status == "unpaid",
            models.customer_invoice.CustomerInvoice.paid_at.is_(None),
            models.customer_invoice.CustomerInvoice.period_end < datetime.combine(today, datetime.min.time()),
        ).all()

        suspended = 0
        for inv in invoices:
            user = db.query(models.user.PPPUser).filter(
                models.user.PPPUser.id == inv.user_id
            ).first()
            if not user:
                continue
            if user.status == "suspended":
                continue  # sudah suspended

            old_status = user.status
            user.status = "suspended"

            db.execute(text("SELECT set_config('app.current_user', :uid, true)"),
                       {"uid": str(user.reseller_id)})
            db.commit()
            db.refresh(user)

            # CoA disconnect (status berubah)
            if user.status != old_status:
                routers = db.query(models.router.MikrotikRouter).filter(
                    models.router.MikrotikRouter.reseller_id == user.reseller_id,
                    models.router.MikrotikRouter.deleted_at.is_(None),
                    models.router.MikrotikRouter.is_active.is_(True),
                ).all()
                for r in routers:
                    try:
                        coa.disconnect_user(user.username, str(r.mgmt_ip), r.radius_secret)
                    except Exception as e:
                        logger.warning(f"[Suspend 1st] CoA fail {user.username} @ {r.mgmt_ip}: {e}")

            # WA suspend
            if user.phone:
                try:
                    msg = (
                        f"Halo {user.full_name or user.username},\n"
                        f"⚠️ Layanan internet Anda *DISUSPEND* dahulu karena tagihan belum dibayar.\n\n"
                        f"Silakan hubungi *tim pembayaran* untuk mengaktifkan kembali layanan jika ingin menunggak."
                    )
                    send_whatsapp(user.phone, msg)
                except Exception as e:
                    logger.error(f"[Suspend 1st] WA gagal {user.username}: {e}")

            suspended += 1

        logger.info(f"[Suspend 1st] suspended={suspended}")

    except Exception as e:
        logger.exception(f"[Suspend 1st] ERROR: {e}")
        db.rollback()
    finally:
        db.close()
