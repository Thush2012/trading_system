import os
import threading
import time
import schedule
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

from telegram import Bot
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

# Master Admin Notifier
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

# Single Bot instance for dispatching messages
bot_instance = Bot(token=Config.TELEGRAM_BOT_TOKEN)

# Parse list of friend chat IDs from .env
raw_subscribers = os.getenv("SUBSCRIBER_CHAT_IDS", "")
SUBSCRIBER_LIST = [cid.strip() for cid in raw_subscribers.split(",") if cid.strip()]

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error: {context.error}")

async def dispatch_signals():
    """
    1. Sends full Master Signal to Admin first.
    2. Automatically sends compressed (TP1 & TP2) signal to selected friends.
    """
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if report.empty:
        return

    for _, row in report.iterrows():
        # --- 1. SEND MASTER SIGNAL TO YOU FIRST ---
        admin_msg = format_vip_signal(row)
        notifier.send_alert(admin_msg)
        log.info(f"Master signal dispatched to Admin for {row['symbol']}.")

        # --- 2. SEND REDUCED SIGNAL TO FRIENDS / SUBSCRIBERS ---
        if SUBSCRIBER_LIST:
            client_msg = format_filtered_partner_signal(row)
            for friend_id in SUBSCRIBER_LIST:
                try:
                    await bot_instance.send_message(
                        chat_id=friend_id,
                        text=client_msg,
                        parse_mode="Markdown"
                    )
                    log.info(f"Reduced signal for {row['symbol']} delivered to subscriber {friend_id}.")
                except Exception as ex:
                    log.error(f"Failed delivering to subscriber {friend_id}: {ex}")

def scheduled_job():
    try:
        asyncio.run(dispatch_signals())
    except Exception as e:
        log.error(f"Scheduled scan failure: {e}")

def scheduler_thread():
    # Scans every 15 minutes automatically
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

    log.info("Telegram engine listening for commands...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("Starting Single-Bot Dual-Market Signal Engine...")

    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    notifier.send_alert(
        "💎 **Dual-Market Trade Engine Online**\n\n"
        "• Primary Receiver: Admin (Master Analytics + TP3)\n"
        f"• Connected Subscribers: {len(SUBSCRIBER_LIST)} recipient(s)\n"
        "• Filter: Automatically sending reduced version (TP1 & TP2 only)"
    )

    run_bot()