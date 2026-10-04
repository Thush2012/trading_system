import threading
import time
import schedule
import asyncio
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.notifier import TelegramNotifier
from core.scanner import LightweightScanner
from telegram_bot import cmd_start, cmd_scan, cmd_info, cmd_guide, handle_button_press, format_vip_signal

log = setup_system_logger("MasterEngine")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error: {context.error}")

async def broadcast_live_setups():
    scanner = LightweightScanner()
    report = await scanner.scan_all()
    if not report.empty:
        for _, row in report.iterrows():
            msg = format_vip_signal(row)
            notifier.send_alert(msg)

def scheduled_job():
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Broadcast failure: {e}")

def scheduler_thread():
    # Scan every 15 minutes during active sessions
    schedule.every(15).minutes.do(scheduled_job)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            log.error(f"Scheduler tick error: {e}")
        time.sleep(1)

def run_bot():
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("guide", cmd_guide))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    app.add_error_handler(error_handler)

    log.info("Starting VIP listener loop...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("Launching VIP Signal Service Engine...")

    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    notifier.send_alert(
        "💎 **VIP Signal Service Engine Active**\n\n"
        "• Multi-Timeframe Quality Filter: Enabled\n"
        "• Auto-Broadcast: Scanning every 15 minutes\n"
        "• Formatted for VIP Client Delivery"
    )

    run_bot()