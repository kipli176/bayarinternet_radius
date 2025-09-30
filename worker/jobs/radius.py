# worker/jobs/radius.py
import time
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.utils import coa

logger = logging.getLogger(__name__)

# antrian retry disconnect sementara (bisa dipindah ke Redis/DB kalau mau durable)
retry_queue = []


def check_nas_status():
    """
    Periksa semua MikrotikRouter aktif di DB, test koneksi RADIUS pakai coa.test_connection().
    """
    db: Session = SessionLocal()
    try:
        routers = db.query(models.router.MikrotikRouter).filter(
            models.router.MikrotikRouter.deleted_at.is_(None),
            models.router.MikrotikRouter.is_active.is_(True),
        ).all()

        for r in routers:
            try:
                ok = coa.test_connection(str(r.mgmt_ip), r.radius_secret)
                if ok:
                    logger.info(f"[NAS check] {r.name} ({r.mgmt_ip}) ✅ OK")
                else:
                    logger.warning(f"[NAS check] {r.name} ({r.mgmt_ip}) ❌ Unexpected reply")
            except Exception as e:
                logger.warning(f"[NAS check] {r.name} ({r.mgmt_ip}) ❌ FAILED: {e}")

    finally:
        db.close()


def safe_disconnect(username: str, nas_ip: str, secret: str, retries: int = 3, delay: int = 2):
    """
    Disconnect user dengan retry. Kalau semua percobaan gagal, simpan ke retry_queue.
    """
    for attempt in range(1, retries + 1):
        try:
            result = coa.disconnect_user(username, nas_ip, secret)
            if result:
                logger.info(f"[CoA] Disconnect {username} @ {nas_ip} ✅ SUCCESS")
            else:
                logger.warning(f"[CoA] Disconnect {username} @ {nas_ip} ❌ NAK")
            return result
        except Exception as e:
            logger.warning(f"[CoA] Disconnect {username} @ {nas_ip} attempt {attempt} FAILED: {e}")
            time.sleep(delay * attempt)  # backoff progresif

    # kalau masih gagal → masuk ke queue
    retry_queue.append({"username": username, "nas_ip": nas_ip, "secret": secret, "retries": retries})
    return False


def process_retry_queue():
    """
    Coba ulang disconnect untuk item yang gagal sebelumnya.
    """
    global retry_queue
    if not retry_queue:
        return

    logger.info(f"[CoA Retry] processing {len(retry_queue)} queued tasks...")
    remaining = []
    for task in retry_queue:
        success = safe_disconnect(task["username"], task["nas_ip"], task["secret"], retries=task["retries"])
        if not success:
            remaining.append(task)  # tetap gagal, simpan lagi

    retry_queue = remaining
