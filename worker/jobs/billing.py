# worker/jobs/billing.py
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from app.database import SessionLocal
from app import models
from app.utils.wa_gateway import send_whatsapp
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
