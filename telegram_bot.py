import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("TelegramBot")

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Scan Market Opportunities")],
        [KeyboardButton("ℹ️ System Status")]
    ],
    resize_keyboard=True
)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Autonomous Market Intelligence Bot*\n\n"
        "• Mode: Pure Cloud/API Feeds (Zero MT5 / Zero Laptop Lag)\n"
        "• Monitored: Forex (EUR, GBP, JPY) & Crypto (BTC, ETH, SOL)\n"
        "• Features: Multi-timeframe trend & momentum alerts\n\n"
        "Tap below to check live setups."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "ℹ️ *SYSTEM HEALTH*\n"
        "• Engine: Active Standalone\n"
        "• Market Data: Real-time Public Feeds\n"
        "• Resource Load: < 1% CPU / Minimal RAM\n"
        "• MT5 Dependencies: Disabled"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning Forex & Crypto pairs...*", parse_mode="Markdown")

    scanner = LightweightScanner()
    report = await scanner.scan_all()

    if report.empty:
        await update.message.reply_text(
            "⚪ *Market Scan Complete:* No high-probability setups meeting ADX + 1H trend filter right now.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        return

    for _, row in report.iterrows():
        msg = (
            f"⚡ *TRADE OPPORTUNITY IDENTIFIED*\n\n"
            f"• Symbol: *{row['symbol']}* ({row['timeframe']})\n"
            f"• Signal: *{row['action']}*\n"
            f"• Entry: `{row['entry']}`\n"
            f"• Suggested Stop Loss: `{row['stop_loss']}`\n"
            f"• Suggested Take Profit: `{row['take_profit']}`\n"
            f"• RSI: `{row['rsi']}` | ADX: `{row.get('adx', 'N/A')}`\n\n"
            f"💡 _Review chart and place manually on your preferred broker/exchange._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⚡ Scan Market Opportunities":
        await cmd_scan(update, context)
    elif text == "ℹ️ System Status":
        await cmd_status(update, context)