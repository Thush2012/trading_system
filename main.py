import os
import threading
import time
import schedule
import asyncio
import logging
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

# Master admin notifier (Bot 1)
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

# Client / Partner dispatch bot (Bot 2)
PARTNER_BOT_TOKEN = os.getenv("PARTNER_BOT_TOKEN")
PARTNER_CHAT_ID = os.getenv("PARTNER_CHAT_ID")

partner_bot = Bot(token=PARTNER_BOT_TOKEN) if PARTNER_BOT_TOKEN else None

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Logs unexpected exceptions in the Telegram polling handler."""
    log.error(f"Telegram polling error encountered: {context.error}")

async def broadcast_live_setups():
    """Scans markets and dispatches signals across both bot channels."""
    # Scheduled scans strictly adhere to the 2-hour symbol cooldown
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if not report.empty:
        for _, row in report.iterrows():
            # 1. Deliver comprehensive master signal to your private admin bot
            admin_msg = format_vip_signal(row)
            notifier.send_alert(admin_msg)

            # 2. Deliver filtered signal (TP1 & TP2 only) to your partner / client channel
            if partner_bot and PARTNER_CHAT_ID:
                try:
                    client_msg = format_filtered_partner_signal(row)
                    await partner_bot.send_message(
                        chat_id=PARTNER_CHAT_ID,
                        text=client_msg,
                        parse_mode="Markdown"
                    )
                    log.info(f"Filtered signal for {row['symbol']} posted to client channel.")
                except Exception as ex:
                    log.error(f"Failed delivering filtered signal via secondary bot: {ex}")

def scheduled_job():
    """Thread-safe runner for asynchronous market scans."""
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Background broadcast cycle failure: {e}")

def scheduler_thread():
    """Background worker running market scans every 15 minutes."""
    schedule.every(15).minutes.do(scheduled_job)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            log.error(f"Scheduler tick error: {e}")
        time.sleep(1)

def run_bot():
    """Initializes and runs the primary interactive Telegram bot."""
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Register command callbacks
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("vip", cmd_sub_info))
    app.add_handler(CommandHandler("rules", cmd_risk_rules))

    # Register custom keyboard buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

    # Register error callback
    app.add_error_handler(error_handler)

    log.info("Primary Telegram bot listener active...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("==================================================")
    log.info("   DUAL-DELIVERY COMMERCIAL SIGNAL SYSTEM LIVE    ")
    log.info("==================================================")

    # Launch autonomous scanner thread
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    secondary_status = "Connected ✅" if (partner_bot and PARTNER_CHAT_ID) else "Not Configured (Optional) ⚠️"

    notifier.send_alert(
        "💎 **Dual-Delivery Engine Online**\n\n"
        "• Master Admin Feed: Active (Full Metrics)\n"
        f"• Client / Partner Bot: {secondary_status}\n"
        "• Scan Frequency: Every 15 minutes\n"
        "• Anti-Spam Cooldown: 2 Hours per Pair"
    )

    run_bot()