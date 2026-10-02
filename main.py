import threading
import time
import schedule
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from core.config import Config
from core.logger import setup_system_logger
from core.notifier import TelegramNotifier
from core.scanner import LightweightScanner
from telegram_bot import cmd_start, cmd_status, cmd_scan, handle_button_press

log = setup_system_logger("MasterEngine")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

async def scan_and_broadcast():
    scanner = LightweightScanner()
    report = await scanner.scan_all()
    if not report.empty:
        for _, row in report.iterrows():
            msg = (
                f"🚨 *AUTOMATED SIGNAL ALERT*\n\n"
                f"• Symbol: *{row['symbol']}* ({row['timeframe']})\n"
                f"• Signal: *{row['action']}*\n"
                f"• Entry: `{row['entry']}`\n"
                f"• SL: `{row['stop_loss']}` | TP: `{row['take_profit']}`\n"
                f"• RSI: `{row['rsi']}` | ADX: `{row.get('adx', 'N/A')}`"
            )
            notifier.send_alert(msg)

def run_scheduled_scan():
    try:
        asyncio.run(scan_and_broadcast())
    except Exception as e:
        log.error(f"Scheduled scan error: {e}")

def scheduler_worker():
    # Scan every 15 minutes
    schedule.every(15).minutes.do(run_scheduled_scan)
    while True:
        schedule.run_pending()
        time.sleep(1)

def run_bot():
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))
    app.run_polling()

if __name__ == "__main__":
    log.info("Starting lightweight alert engine...")

    t = threading.Thread(target=scheduler_worker, daemon=True)
    t.start()

    notifier.send_alert(
        "🟢 *Market Alert Engine Live*\n"
        "• Mode: Lightweight Standalone\n"
        "• MT5 / Windows Watcher Hooks: Removed\n"
        "• System consumption reduced to baseline."
    )

    run_bot()