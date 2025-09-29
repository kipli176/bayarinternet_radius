import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from sched import scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler 
from worker.jobs import users, billing
from datetime import datetime, timedelta

# 🔹 konfigurasi logging dengan rotasi harian
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# file handler → rotasi tiap hari, simpan max 7 hari
file_handler = TimedRotatingFileHandler(
    "./app/logs/worker.log", when="midnight", interval=1, backupCount=7, encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# console handler → tampil di docker logs
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger("worker")

async def main():
    scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

    scheduler.add_job(
        billing.generate_invoices_h_minus_7,
        "date",
        run_date=datetime.utcnow() + timedelta(minutes=5),
        kwargs={"force": True}
    )
    scheduler.add_job(billing.generate_invoices_h_minus_7, "cron", hour=7, minute=0)

    # 🔔 reminder masa aktif user (H-3 sebelum active_until)
    scheduler.add_job(users.remind_users_before_expiry, "cron", hour=8, minute=0)

    # 🔔 reminder H-3 sebelum akhir bulan
    scheduler.add_job(users.remind_users_end_of_month, "cron", hour=9, minute=0)

    # 🧾 cek invoice overdue tiap awal bulan
    scheduler.add_job(billing.mark_overdue_invoices, "cron", day=1, hour=7, minute=0)

    scheduler.start()
    logger.info("Worker started...")

    # keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
