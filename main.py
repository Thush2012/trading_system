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
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

# Target chat/channel ID for your friend or clients
PARTNER_CHAT_ID = os.getenv("PARTNER_CHAT_ID")
standalone_bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error: {context.error}")

async def broadcast_live_setups():
    """Scans markets and dispatches dual-format alerts."""
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if not report.empty:
        for _, row in report.iterrows():
            # 1. Deliver full master signal to your private admin chat
            admin_msg = format_vip_signal(row)
            notifier.send_alert(admin_msg)

            # 2. Deliver filtered signal (TP1 & TP2 only) to your partner/clients
            if PARTNER_CHAT_ID:
                try:
                    client_msg = format_filtered_partner_signal(row)
                    await standalone_bot.send_message(
                        chat_id=PARTNER_CHAT_ID,
                        text=client_msg,
                        parse_mode="Markdown"
                    )
                    log.info(f"Filtered signal for {row['symbol']} sent to partner/client channel.")
                except Exception as ex:
                    log.error(f"Failed sending filtered signal to partner: {ex}")

def scheduled_job():
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Background broadcast error: {e}")

def scheduler_thread():
    # Runs the autonomous scan every 15 minutes
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

    log.info("VIP Signal Engine listening for Telegram interactions...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("Launching Dual-Delivery VIP Signal Engine...")

    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    notifier.send_alert(
        "💎 **Dual-Delivery Signal Engine Online**\n\n"
        "• Admin Channel: Full Master Metrics (TP1, TP2, TP3)\n"
        f"• Partner/Client Delivery: {'Configured ✅' if PARTNER_CHAT_ID else 'Awaiting PARTNER_CHAT_ID ⚠️'}\n"
        "• Client Format: Compressed (Entry Range, SL, TP1 & TP2 only)"
    )

    run_bot()