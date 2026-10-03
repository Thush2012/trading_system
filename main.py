import threading
import time
import schedule
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.notifier import TelegramNotifier
from core.scanner import LightweightScanner
from telegram_bot import cmd_start, cmd_status, cmd_scan, handle_button_press, format_signal_message

log = setup_system_logger("MasterEngine")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram error encountered: {context.error}")

async def scan_and_broadcast():
    """Runs a periodic background scan and pushes formatted Forex & Binance Crypto alerts."""
    scanner = LightweightScanner()
    report = await scanner.scan_all()
    if not report.empty:
        for _, row in report.iterrows():
            msg = format_signal_message(row)
            notifier.send_alert(msg)

def run_scheduled_scan():
    try:
        asyncio.run(scan_and_broadcast())
    except Exception as e:
        log.error(f"Scheduled scan error: {e}")

def scheduler_worker():
    schedule.every(15).minutes.do(run_scheduled_scan)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            log.error(f"Scheduler tick error: {e}")
        time.sleep(1)

def run_bot():
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    app.add_error_handler(error_handler)

    log.info("Starting Telegram polling listener...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("Starting lightweight multi-target alert engine...")

    t = threading.Thread(target=scheduler_worker, daemon=True)
    t.start()

    notifier.send_alert(
        "🟢 *Multi-TP Signal Engine Live*\n"
        "• Targets: TP1, TP2, TP3 (Scale-Out Enabled)\n"
        "• Crypto Formatted: Binance USDT-M / Spot\n"
        "• Background Scans: Active every 15 minutes"
    )

    run_bot()