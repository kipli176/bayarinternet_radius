# worker/jobs/billing.py
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from app.database import SessionLocal
from app import models
from app.utils.wa_gateway import send_whatsapp, format_invoice_generated_reseller
from decimal import Decimal, ROUND_HALF_UP
# OPSIONAL: aktifkan CoA kalau sudah siap
from app.utils import coa
import logging

logger = logging.getLogger("worker.jobs.billing")

def mark_overdue_invoices():
    """
    Tanggal 1 setiap bulan:
      - Semua customer invoice yang belum paid dan period_end < today => set 'overdue'
      - User terkait => set status 'suspended'
      - Kirim WA pemberitahuan suspend
      - (Opsional) Kirim Disconnect-Request (CoA) agar sesi langsung terputus
    """
    db: Session = SessionLocal()
    try:
        # gunakan UTC date; scheduler kita timezone Asia/Jakarta di main.py
        today = datetime.utcnow().date()

        # ambil semua invoice customer yang sudah melewati period_end & belum paid
        invoices = db.query(models.customer_invoice.CustomerInvoice).filter(
            and_(
                models.customer_invoice.CustomerInvoice.status != "paid",
                models.customer_invoice.CustomerInvoice.period_end < today
            )
        ).all()

        logger.info(f"[mark_overdue_invoices] {len(invoices)} invoice ditemukan untuk ditandai overdue.")

        for inv in invoices:
            # tandai overdue (hindari overwrite jika sudah overdue)
            if inv.status != "overdue":
                inv.status = "overdue"

            # suspend user
            user = db.query(models.user.PPPUser).filter(
                models.user.PPPUser.id == inv.user_id
            ).first()

            # ambil reseller (untuk CoA & info lain)
            reseller = db.query(models.reseller.Reseller).filter(
                models.reseller.Reseller.id == inv.reseller_id
            ).first()

            if user and user.status != "suspended":
                user.status = "suspended"

                logger.info(f"[mark_overdue_invoices] User {user.username} disuspend (invoice {inv.id}).")

                # kirim WA info suspend
                if user.phone:
                    try:
                        period = f"{inv.period_start.strftime('%d-%m-%Y')} s/d {inv.period_end.strftime('%d-%m-%Y')}"
                        amount = f"Rp {int(inv.amount):,}"
                        msg = (
                            f"Halo {user.full_name or user.username},\n"
                            f"⚠️ Layanan internet Anda *DISUSPEND* karena tagihan belum dibayar.\n\n"
                            f"📄 Periode: {period}\n"
                            f"💰 Tagihan: {amount}\n\n"
                            f"Silakan lakukan pembayaran untuk mengaktifkan kembali layanan. Terima kasih 🙏"
                        )
                        send_whatsapp(user.phone, msg)

                        logger.info(f"[mark_overdue_invoices] WA notif suspend terkirim ke {user.username} ({user.phone})")
                    except Exception as e:
                        logger.error(f"[mark_overdue_invoices] Gagal kirim WA ke {user.username}: {e}")

                # OPSIONAL: CoA disconnect semua NAS milik reseller
                if reseller:
                    routers = db.query(models.router.MikrotikRouter).filter(
                        models.router.MikrotikRouter.reseller_id == reseller.id,
                        models.router.MikrotikRouter.deleted_at.is_(None),
                        models.router.MikrotikRouter.is_active.is_(True)
                    ).all()
                    for r in routers:
                        try:
                            coa.disconnect_user(
                                username=user.username,
                                nas_ip=str(r.mgmt_ip),
                                secret=r.radius_secret
                            )
                        except Exception as e:
                            # log saja; jangan menghalangi commit suspend
                            print(f"CoA failed {user.username} @ {r.mgmt_ip}: {e}")

        db.execute(text("SELECT set_config('app.current_user', :uid, true)"), {"uid": str(reseller.id)})
        db.commit()

    except Exception as e:
        logger.exception(f"[mark_overdue_invoices] ERROR: {e}")
        print(f"[worker] mark_overdue_invoices error: {e}")
        db.rollback()
    finally:
        db.close()




def generate_invoice_for_reseller(db: Session, reseller, period_start: datetime, period_end: datetime):
    """
    Generate invoice untuk reseller (jika belum ada, atau sudah ada tapi belum paid).
    Return invoice yang baru dibuat atau existing unpaid.
    """
    # cek apakah invoice periode ini sudah ada
    existing = db.query(models.invoice.Invoice).filter(
        models.invoice.Invoice.reseller_id == reseller.id,
        models.invoice.Invoice.period_start == period_start,
        models.invoice.Invoice.period_end == period_end
    ).first()

    if existing:
        if existing.status != "paid":
            logger.info(f"Invoice reseller {reseller.name} periode {period_start:%Y-%m} sudah ada & belum paid")
            return existing
        logger.info(f"Invoice reseller {reseller.name} periode {period_start:%Y-%m} sudah ada & sudah paid")
        return None

    # hitung jumlah user aktif
    users_count = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.status == "active"
    ).count()

    # hitung harga & subtotal
    unit_price = Decimal(str(reseller.price_per_user or 0))
    subtotal = (Decimal(users_count) * unit_price).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    # volume pricing
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

    # pajak 10%
    tax = ((subtotal - discount) * Decimal("0.10")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    # total
    total = (subtotal - discount + tax).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    # meta snapshot
    meta = {
        "company_name": reseller.company_name,
        "alamat": reseller.alamat,
        "logo": reseller.logo,
        "price_per_user": float(unit_price),
        "currency": reseller.currency,
        "users_count": users_count,
        "volume_pricing": reseller.volume_pricing,
    }

    invoice = models.invoice.Invoice(
        reseller_id=reseller.id,
        period_start=period_start,
        period_end=period_end,
        users_count=users_count,
        unit_price=unit_price,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=total,
        currency=reseller.currency or "IDR",
        status="unpaid",
        meta=meta
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # kirim WA ke reseller
    if reseller.phone:
        try:
            msg = format_invoice_generated_reseller(reseller, invoice)
            send_whatsapp(reseller.phone, msg)
            logger.info(f"WA invoice dikirim ke reseller {reseller.name} ({reseller.phone})")
        except Exception as e:
            logger.error(f"Gagal kirim WA ke reseller {reseller.name}: {e}")

    logger.info(f"Invoice reseller {reseller.name} periode {period_start:%Y-%m} berhasil dibuat")
    return invoice


def generate_invoices_h_minus_7(today: date | None = None, force: bool = False):
    if today is None:
        today = datetime.utcnow().date()

    # hitung last day bulan ini
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    last_day = next_month - timedelta(days=1)

    # skip kalau bukan H-7, kecuali dipaksa
    if not force and today != last_day - timedelta(days=7):
        return

    period_start = datetime.combine(today.replace(day=1), datetime.min.time())
    period_end = datetime.combine(last_day, datetime.min.time())

    db: Session = SessionLocal()
    try:
        resellers = db.query(models.reseller.Reseller).filter(
            models.reseller.Reseller.is_active.is_(True),
            models.reseller.Reseller.deleted_at.is_(None)
        ).all()

        for reseller in resellers:
            generate_invoice_for_reseller(db, reseller, period_start, period_end)

        logger.info("[H-7] Generate invoices selesai")
    except Exception as e:
        logger.exception(f"[H-7] ERROR: {e}")
        db.rollback()
    finally:
        db.close()
