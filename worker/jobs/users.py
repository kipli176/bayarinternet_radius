from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.utils.wa_gateway import send_whatsapp, format_reminder_active_until, format_reminder_end_of_month
import logging

logger = logging.getLogger("worker.jobs.users")

def remind_users_before_expiry():
    db: Session = SessionLocal()
    try:
        today = datetime.utcnow().date()
        target_date = today + timedelta(days=3)

        users = db.query(models.user.PPPUser).filter(
            models.user.PPPUser.active_until == target_date,
            models.user.PPPUser.status == "active"
        ).all()

        logger.info(f"[remind_users_before_expiry] {len(users)} user ditemukan untuk reminder (H-3).")

        for u in users:
            profile = db.query(models.profile.PPPProfile).filter(
                models.profile.PPPProfile.id == u.profile_id
            ).first()
            if u.phone and profile:
                msg = format_reminder_active_until(u, profile)
                try:
                    send_whatsapp(u.phone, msg)
                    logger.info(f"[remind_users_before_expiry] Reminder terkirim ke {u.username} ({u.phone})")
                except Exception as e:
                    logger.error(f"[remind_users_before_expiry] Gagal kirim WA ke {u.username}: {e}")

    except Exception as e:
        logger.exception(f"[remind_users_before_expiry] ERROR: {e}")
    finally:
        db.close()


def remind_users_end_of_month():
    db: Session = SessionLocal()
    try:
        today = datetime.utcnow().date()
        last_day = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        target_date = last_day - timedelta(days=3)

        if today == target_date:
            users = db.query(models.user.PPPUser).filter(
                models.user.PPPUser.status == "active"
            ).all()

            logger.info(f"[remind_users_end_of_month] {len(users)} user aktif dicek untuk reminder (H-3 sebelum akhir bulan).")

            for u in users:
                profile = db.query(models.profile.PPPProfile).filter(
                    models.profile.PPPProfile.id == u.profile_id
                ).first()
                if u.phone and profile:
                    msg = format_reminder_end_of_month(u, profile)
                    try:
                        send_whatsapp(u.phone, msg)
                        logger.info(f"[remind_users_end_of_month] Reminder terkirim ke {u.username} ({u.phone})")
                    except Exception as e:
                        logger.error(f"[remind_users_end_of_month] Gagal kirim WA ke {u.username}: {e}")

    except Exception as e:
        logger.exception(f"[remind_users_end_of_month] ERROR: {e}")
    finally:
        db.close()
