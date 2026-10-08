import os
from dotenv import load_dotenv

# Load .env variables immediately
load_dotenv()

import threading
import time
import schedule
import asyncio
import logging
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from telegram_bot import (
    cmd_start,
    cmd_scan,
    cmd_status,
    cmd_risk_rules,
    handle_button_press,
    format_signal_message,
    global_scanner
)

log = setup_system_logger("MasterEngine")

# Single bot instance delivering strictly to you
bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
ADMIN_CHAT_ID = Config.TELEGRAM_CHAT_ID

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error: {context.error}")

async def broadcast_live_setups():
    """Runs periodic scans and pushes setups directly to your chat."""
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if not report.empty:
        for _, row in report.iterrows():
            msg = format_signal_message(row)
            try:
                await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg, parse_mode="Markdown")
                log.info(f"Signal for {row['symbol']} delivered to admin.")
            except Exception as e:
                log.error(f"Failed delivering alert: {e}")

def scheduled_job():
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Scheduled scan failure: {e}")

def scheduler_thread():
    # Scan every 15 minutes
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
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("rules", cmd_risk_rules))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    app.add_error_handler(error_handler)

    log.info("Dual Market Trade Engine listening...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("==================================================")
    log.info("        DUAL MARKET TRADE ENGINE (DIRECT)         ")
    log.info("==================================================")

    # Launch background scheduler
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    async def notify_boot():
        startup_text = (
            "💎 **Dual Market Trade Engine Online**\n\n"
            "• Mode: Standalone Direct Alert Terminal\n"
            "• Auto Scan: Active Every 15 Minutes\n"
            "• Exits: TP1, TP2, TP3 Multi-Target Enabled"
        )
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_text, parse_mode="Markdown")
        except Exception as ex:
            log.error(f"Could not send boot alert: {ex}")

    asyncio.run(notify_boot())
    run_bot()