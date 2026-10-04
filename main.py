import threading
import time
import schedule
import asyncio
import logging
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
    global_scanner
)

log = setup_system_logger("MasterEngine")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram polling error: {context.error}")

async def broadcast_live_setups():
    # Regular 15-minute background run obeys cooldowns (no spam)
    report = await global_scanner.scan_all(bypass_cooldown=False)
    if not report.empty:
        for _, row in report.iterrows():
            msg = format_vip_signal(row)
            notifier.send_alert(msg)

def scheduled_job():
    try:
        asyncio.run(broadcast_live_setups())
    except Exception as e:
        log.error(f"Background broadcast error: {e}")

def scheduler_thread():
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
    log.info("Launching VIP Commercial Signal Service...")

    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()

    notifier.send_alert(
        "💎 **VIP Commercial Signal Engine Online**\n\n"
        "• Anti-Spam Cooldown: 2 Hours per Pair\n"
        "• Flexible Entry Zones: Active\n"
        "• 3-Tier Take Profit Scale-Outs: Enabled"
    )

    run_bot()