import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from sched import scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler 
from worker.jobs import customer_billing, billing, radius
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
    # scheduler.add_job(
    #     billing.mark_overdue_invoices,
    #     "interval",
    #     minutes=2
    # )
    # scheduler.add_job(
    #     billing.generate_invoices_h_minus_7,
    #     "interval",
    #     minutes=3,
    #     kwargs={"force": True}
    # )
    scheduler.add_job(billing.generate_invoices_h_minus_7, "cron", hour=7, minute=0)

    # 🧾 cek invoice overdue tiap awal bulan
    scheduler.add_job(billing.mark_overdue_invoices, "cron", day=1, hour=7, minute=0)

    # H-3 sebelum active_until (jalan tiap hari, fungsi sendiri yang memutuskan siapa yang H-3)
    scheduler.add_job(customer_billing.generate_customer_invoices_h_minus_3, "cron", hour=1)

    # H-5 sebelum akhir bulan (fungsi cek sendiri apakah hari ini = H-5 EOM)
    scheduler.add_job(customer_billing.remind_unpaid_h_minus_5_eom, "cron", hour=8)

    # Tanggal 1: suspend semua yang masih unpaid
    scheduler.add_job(customer_billing.suspend_unpaid_on_first, "cron", day=1, hour=7)


    # cek NAS tiap 10 menit
    scheduler.add_job(radius.check_nas_status, "interval", minutes=5)

    # retry queue disconnect tiap 1 menit
    scheduler.add_job(radius.process_retry_queue, "interval", minutes=1)

    scheduler.start()
    logger.info("Worker started...")

    # keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
