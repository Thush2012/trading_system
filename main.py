import os
import threading
import time
import schedule
import asyncio
import logging
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.notifier import TelegramNotifier
from telegram_bot import (
    cmd_start,
    cmd_scan,
    cmd_sub_info,
    cmd_risk_rules,
    handle_button_press,
    format_vip_signal,
    format_filtered_partner_signal,
    global_scanner
)

log = setup_system_logger("MasterEngine")

# Master Admin Notifier (Sends full details to you)
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

# Parse list of friend/client chat IDs
raw_client_ids = os.getenv("CLIENT_CHAT_IDS", "")
CLIENT_LIST = [cid.strip() for cid in raw_client_ids.split(",") if cid.strip()]

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error encountered: {context.error}")

async def broadcast_live_setups():
    """Scans markets, delivers master signal to admin, and pushes reduced signal to friends."""
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if not report.empty:
        for _, row in report.iterrows():
            # 1. Send the full master signal to you (TP1, TP2, TP3, RSI)
            admin_msg = format_vip_signal(row)
            notifier.send_alert(admin_msg)

            # 2. Automatically dispatch the reduced signal (TP1, TP2 only) to your friends/clients
            if CLIENT_LIST:
                reduced_msg = format_filtered_partner_signal(row)
                for client_id in CLIENT_LIST:
                    try:
                        # Reuses the exact same bot instance
                        await notifier.bot.send_message(
                            chat_id=client_id,
                            text=reduced_msg,
                            parse_mode="Markdown"
                        )
                        log.info(f"Reduced signal delivered to recipient: {client_id}")
                    except Exception as e:
                        log.error(f"Failed delivering to recipient {client_id}: {e}")

def scheduled_job():
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Background broadcast cycle failure: {e}")

def scheduler_thread():
    # Scans every 15 minutes
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
    app.add_handler(CommandHandler("vip", cmd_sub_info))
    app.add_handler(CommandHandler("rules", cmd_risk_rules))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    app.add_error_handler(error_handler)

    log.info("Primary Telegram bot listener active...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("Starting Multi-Tier Signal Dispatcher...")

    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    notifier.send_alert(
        "💎 **Signal Engine Online**\n\n"
        "• Master Admin Feed: Active (Full Metrics + TP1/TP2/TP3)\n"
        f"• Connected Client Recipients: {len(CLIENT_LIST)}\n"
        "• Client Format: Auto-reduced (Entry Range, SL, TP1 & TP2 only)\n"
        "• Scan Frequency: Every 15 minutes"
    )

    run_bot()