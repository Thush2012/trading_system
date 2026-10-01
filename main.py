import threading
import time
import schedule
import asyncio
import traceback
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from core.config import Config
from core.logger import setup_system_logger
from core.notifier import TelegramNotifier
from core.mt5_connection import connect_mt5
from run_live_engine import run_trading_cycle
from telegram_bot import (
    cmd_start,
    cmd_status,
    cmd_scan,
    cmd_closeall,
    cmd_positions,
    handle_button_press,
    handle_button_callback
)

log = setup_system_logger("MasterEngine")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

# --- SCHEDULED BROADCASTS (Sri Lanka Local Time) ---
def morning_briefing():
    """Daily 08:30 LK Time Briefing."""
    if not connect_mt5():
        return
    acc = mt5.account_info()
    positions = mt5.positions_get()
    open_count = len(positions) if positions else 0

    msg = (
        "🌅 *GOOD MORNING: DAILY TRADING BRIEF* 🌅\n\n"
        f"• Account Balance: `${acc.balance:,.2f}`\n"
        f"• Available Equity: `${acc.equity:,.2f}`\n"
        f"• Active Positions: `{open_count}`\n\n"
        "💡 _Autonomous scanners are checking the market every 5 minutes. Major volume starts with London Open at 13:30._"
    )
    notifier.send_alert(msg)

def nightly_summary():
    """Daily 22:30 LK Time Performance Ledger."""
    if not connect_mt5():
        return
    acc = mt5.account_info()
    now = datetime.now(timezone.utc)
    deals = mt5.history_deals_get(now - timedelta(hours=18), now)
    
    daily_pnl = 0.0
    wins = 0
    losses = 0

    if deals:
        for d in deals:
            if d.entry == 1:  # Deal closed
                daily_pnl += d.profit
                if d.profit > 0:
                    wins += 1
                elif d.profit < 0:
                    losses += 1

    total_closed = wins + losses
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0
    pnl_sign = "+$" if daily_pnl >= 0 else "-$"

    msg = (
        "🌙 *NIGHTLY PERFORMANCE SUMMARY* 🌙\n\n"
        f"• Realized PnL Today: *{pnl_sign}{abs(daily_pnl):,.2f}*\n"
        f"• Closed Trades: `{total_closed}` (Wins: `{wins}` | Losses: `{losses}`)\n"
        f"• Win Rate Today: `{win_rate:.1f}%`\n"
        f"• Closing Equity: `${acc.equity:,.2f}`\n\n"
        "💤 _Headless engine remains active overnight monitoring open positions and crypto swings._"
    )
    notifier.send_alert(msg)

def alert_london_open():
    """Alerts London session open at 13:30 LK time."""
    notifier.send_alert(
        "🇬🇧 *PRIME MARKET SESSION: LONDON OPEN* 🇬🇧\n\n"
        "• Time: 13:30 LK Time\n"
        "• High volume influx across EURUSD & GBPUSD. Look for breakout continuation."
    )

def alert_ny_overlap():
    """Alerts NY/London overlap peak session at 18:30 LK time."""
    notifier.send_alert(
        "🌟 *GOLDEN TRADING SESSION: NY/LONDON OVERLAP* 🌟\n\n"
        "• Time: 18:30 LK Time\n"
        "• Peak liquidity across Forex and Crypto pairs."
    )

def send_heartbeat():
    """Sends a subtle health check every 6 hours."""
    if connect_mt5():
        notifier.send_alert("💚 *System Heartbeat:* Headless MT5 connected. 24/7 background scanners operational.")

# --- BACKGROUND ENGINE WORKER ---
def execute_safe_cycle():
    """Wrapper to run the asynchronous live trading cycle safely."""
    try:
        asyncio.run(run_trading_cycle())
    except Exception as e:
        log.error(f"Error during live cycle execution: {e}\n{traceback.format_exc()}")

def scheduler_thread_worker():
    """Runs continuous background schedule loops."""
    log.info("Continuous background scheduler active.")
    execute_safe_cycle()

    # Dynamic 5-minute autonomous scanning
    schedule.every(5).minutes.do(execute_safe_cycle)

    # Session broadcasts (Sri Lanka Time)
    schedule.every().day.at("08:30").do(morning_briefing)
    schedule.every().day.at("13:30").do(alert_london_open)
    schedule.every().day.at("18:30").do(alert_ny_overlap)
    schedule.every().day.at("22:30").do(nightly_summary)

    # Health check
    schedule.every(6).hours.do(send_heartbeat)

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            log.error(f"Scheduler tick error: {e}")
        time.sleep(1)

# --- TELEGRAM BOT INTERFACE ---
def run_telegram_bot():
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("closeall", cmd_closeall))
    app.add_handler(CommandHandler("positions", cmd_positions))

    # Persistent thumb keyboard button handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

    # Inline button callback handler (for one-tap trade executions & dismissals)
    app.add_handler(CallbackQueryHandler(handle_button_callback))

    app.run_polling()

if __name__ == "__main__":
    log.info("==================================================")
    log.info("  AUTONOMOUS 24/7 TRADING ENGINE (HEADLESS MODE)")
    log.info("==================================================")

    # Start the continuous background trading cycle in a daemon thread
    daemon_thread = threading.Thread(target=scheduler_thread_worker, daemon=True)
    daemon_thread.start()

    notifier.send_alert(
        "🟢 *24/7 Trading System Live*\n"
        "• Mode: Headless Background\n"
        "• Scan frequency: Every 5 minutes\n"
        "• Interactive execution buttons active in Telegram."
    )

    try:
        run_telegram_bot()
    except KeyboardInterrupt:
        log.warning("Shutdown signal received.")
        notifier.send_alert("🔴 *Trading Engine Offline*")