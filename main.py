import os
import logging
from dotenv import load_dotenv

# Load .env variables immediately
load_dotenv()

from telegram import Update
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
ADMIN_CHAT_ID = Config.TELEGRAM_CHAT_ID

logging.getLogger("telegram").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Logs any polling or runtime errors."""
    log.error(f"Telegram error encountered: {context.error}")

async def scheduled_scan_job(context: ContextTypes.DEFAULT_TYPE):
    """Background scanner executed automatically by Telegram's JobQueue."""
    try:
        log.info("Running automated 15-minute background market scan...")
        report = await global_scanner.scan_all(bypass_cooldown=False)
        if not report.empty:
            for _, row in report.iterrows():
                msg = format_signal_message(row)
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=msg,
                    parse_mode="Markdown"
                )
                log.info(f"Signal for {row['symbol']} delivered to admin.")
    except Exception as e:
        log.error(f"Automated scan failure: {e}")

async def post_init_hook(application):
    """Runs inside the bot's own event loop right after initialization."""
    log.info("Master bot connected. Dispatching boot alert...")
    startup_text = (
        "💎 **Dual Market Trade Engine Online**\n\n"
        "• Mode: Standalone Direct Alert Terminal\n"
        "• Auto Scan: Active Every 15 Minutes\n"
        "• Exits: TP1, TP2, TP3 Multi-Target Enabled\n"
        "• Listener: Ready for commands"
    )
    try:
        await application.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=startup_text,
            parse_mode="Markdown"
        )
    except Exception as ex:
        log.error(f"Could not send boot alert: {ex}")

def main():
    log.info("==================================================")
    log.info("        DUAL MARKET TRADE ENGINE (DIRECT)         ")
    log.info("==================================================")

    # Build Application
    app = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init_hook)
        .build()
    )

    # Register Command & Message Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("rules", cmd_risk_rules))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    app.add_error_handler(error_handler)

    # Schedule 15-minute background scans using built-in JobQueue
    if app.job_queue:
        app.job_queue.run_repeating(
            scheduled_scan_job,
            interval=900,  # 900 seconds = 15 minutes
            first=60       # First scan runs 60 seconds after startup
        )
        log.info("15-minute background scan scheduled successfully.")

    log.info("Dual Market Trade Engine listening for updates...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()