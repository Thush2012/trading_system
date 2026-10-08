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
    format_master_signal,
    format_reduced_client_signal,
    global_scanner
)

log = setup_system_logger("MasterEngine")

# Single bot instance used for listening and broadcasting
bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
ADMIN_CHAT_ID = Config.TELEGRAM_CHAT_ID

# Parse comma-separated list of friend/client IDs
recipients_raw = os.getenv("CLIENT_RECIPIENTS", "")
CLIENT_LIST = [cid.strip() for cid in recipients_raw.split(",") if cid.strip()]

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error: {context.error}")

async def broadcast_live_setups():
    """Scans markets and dispatches signals: full to Admin, reduced to friends."""
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if not report.empty:
        for _, row in report.iterrows():
            # 1. Send full institutional signal to you (Admin)
            master_msg = format_master_signal(row)
            try:
                await bot.send_message(chat_id=ADMIN_CHAT_ID, text=master_msg, parse_mode="Markdown")
            except Exception as e:
                log.error(f"Failed sending master alert to admin: {e}")

            # 2. Automatically dispatch reduced signal (TP1 & TP2 only) to friends
            if CLIENT_LIST:
                reduced_msg = format_reduced_client_signal(row)
                for client_id in CLIENT_LIST:
                    try:
                        await bot.send_message(chat_id=client_id, text=reduced_msg, parse_mode="Markdown")
                        log.info(f"Reduced signal for {row['symbol']} delivered to client: {client_id}")
                    except Exception as ex:
                        log.error(f"Failed delivering to client {client_id}: {ex}")

def scheduled_job():
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Scheduled scan failure: {e}")

def scheduler_thread():
    # Automatically scan every 15 minutes
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

    log.info("Master Engine listening for Telegram interactions...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("==================================================")
    log.info("        DUAL MARKET TRADE ENGINE (MASTER)         ")
    log.info("==================================================")

    # Launch background scheduler
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    async def notify_boot():
        startup_text = (
            "💎 **Dual Market Trade Engine Online**\n\n"
            "• Mode: Standalone Master Engine\n"
            f"• Client Recipient Count: `{len(CLIENT_LIST)}`\n"
            "• Auto Scan: Active Every 15 Minutes\n"
            "• Reduced Forwarding (TP1 & TP2): Enabled"
        )
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_text, parse_mode="Markdown")
        except Exception as ex:
            log.error(f"Could not send boot alert: {ex}")

    asyncio.run(notify_boot())
    run_bot()