# app/utils/wa_gateway.py
import requests
import os
from datetime import datetime

WA_GATEWAY_URL = os.getenv("WA_GATEWAY_URL", "https://blast.sukipli.work/send-message")

def send_whatsapp(number: str, message: str) -> bool:
    """
    Kirim pesan WhatsApp via WA Gateway.
    """
    payload = {
        "number": number,
        "message": message
    }
    try:
        resp = requests.post(WA_GATEWAY_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("status") == "sent"
        return False
    except Exception as e:
        print(f"WA error: {e}")
        return False

def format_invoice_paid_message(invoice, is_customer=False, user=None, profile=None):
    if is_customer and user and profile:
        months_paid = max(1, round(invoice.amount / float(profile.price or 1)))
        new_until = user.active_until.strftime("%d-%m-%Y") if user.active_until else "-"

        msg = (
            f"Halo {user.full_name or user.username},\n"
            f"✅ Pembayaran Internet Anda sudah diterima.\n\n"
            f"📄 Paket: {profile.name}\n"
            f"💰 Jumlah Dibayar: Rp {int(invoice.amount):,}\n"
            f"🗓️ Periode: {months_paid} bulan\n"
            f"📌 Aktif hingga: {new_until}\n\n"
            f"Terima kasih telah mempercayai layanan kami 🙏"
        )
        return msg
    else:
        return (
            f"Halo {user.name},\n"
            f"💳 Invoice Reseller telah dibayar ✅\n\n"
            f"👥 Jumlah User: {invoice.users_count}\n"
            f"💰 Total: Rp {int(invoice.total):,}\n"
            f"📅 Periode: {invoice.period_start.strftime('%d-%m-%Y')} s/d {invoice.period_end.strftime('%d-%m-%Y')}\n\n"
            f"Terima kasih 🙏"
        )
    
def format_reminder_active_until(user, profile):
    due = user.active_until.strftime("%d-%m-%Y") if user.active_until else "-"
    return (
        f"Halo {user.full_name or user.username},\n"
        f"🔔 Masa aktif internet Anda akan berakhir pada {due}.\n\n"
        f"📄 Paket: {profile.name}\n"
        f"💰 Harga per bulan: Rp {int(profile.price):,}\n\n"
        f"Segera lakukan pembayaran agar layanan tetap aktif tanpa gangguan 🙏"
    )



def format_reminder_end_of_month(user, profile):
    end_month = datetime.utcnow().replace(day=28).strftime("%d-%m-%Y")
    return (
        f"Halo {user.full_name or user.username},\n"
        f"🔔 Tagihan internet bulan ini belum terbayar.\n\n"
        f"📄 Paket: {profile.name}\n"
        f"💰 Harga per bulan: Rp {int(profile.price):,}\n"
        f"🗓️ Jatuh tempo: {end_month}\n\n"
        f"Segera lakukan pembayaran sebelum akhir bulan agar layanan tidak terputus 🙏"
    )
