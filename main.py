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
from telegram_bot import cmd_start, cmd_status, cmd_scan, handle_button_press

log = setup_system_logger("MasterEngine")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

# Configure Telegram log levels for console output
logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Logs any errors triggered by Telegram updates."""
    log.error(f"Telegram error encountered: {context.error}")

async def scan_and_broadcast():
    """Runs a periodic background scan and pushes active Forex and Crypto setups."""
    scanner = LightweightScanner()
    report = await scanner.scan_all()
    if not report.empty:
        for _, row in report.iterrows():
            msg = (
                f"🚨 {row['icon']} *AUTOMATED {row['asset_class'].upper()} SIGNAL*\n\n"
                f"• Market: *{row['asset_class']}*\n"
                f"• Symbol: *{row['symbol']}* ({row['timeframe']})\n"
                f"• Signal: *{row['action']}*\n"
                f"• Entry: `{row['entry']}`\n"
                f"• Stop Loss: `{row['stop_loss']}`\n"
                f"• Take Profit: `{row['take_profit']}`\n"
                f"• RSI: `{row['rsi']}`"
            )
            notifier.send_alert(msg)

def run_scheduled_scan():
    """Executes the async scan safely from the scheduler thread."""
    try:
        asyncio.run(scan_and_broadcast())
    except Exception as e:
        log.error(f"Scheduled scan error: {e}")

def scheduler_worker():
    """Background worker executing scans every 15 minutes."""
    schedule.every(15).minutes.do(run_scheduled_scan)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            log.error(f"Scheduler tick error: {e}")
        time.sleep(1)

def run_bot():
    """Starts the Telegram bot with clear polling and handler routing."""
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan", cmd_scan))

    # Register bottom custom thumb keyboard buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

    # Error handling callback
    app.add_error_handler(error_handler)

    log.info("Starting Telegram polling listener...")
    # drop_pending_updates flushes stale unhandled requests from previous offline periods
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    log.info("Starting lightweight alert engine...")

    # Launch the scheduler in a background daemon thread
    t = threading.Thread(target=scheduler_worker, daemon=True)
    t.start()

    notifier.send_alert(
        "🟢 *Market Alert Engine Live*\n"
        "• Mode: Lightweight Standalone\n"
        "• Monitored: 💱 Forex & 🪙 Crypto\n"
        "• Auto Scan: Active every 15 minutes\n"
        "• MT5 / Windows Watcher Hooks: Fully removed"
    )

    run_bot()