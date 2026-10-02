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
        "• Monitored Markets: 💱 Forex & 🪙 Crypto\n"
        "• Mode: Zero-lag Lightweight Cloud Feeds\n\n"
        "Tap below to check live setups."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "ℹ️ *SYSTEM HEALTH*\n"
        "• Engine: Active Standalone\n"
        "• Market Data: Live Yahoo Finance Feeds\n"
        "• Asset Coverage: Forex (EUR, GBP, JPY) + Crypto (BTC, ETH, SOL)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning Forex & Crypto pairs...*", parse_mode="Markdown")

    scanner = LightweightScanner()
    report = await scanner.scan_all()

    if report.empty:
        await update.message.reply_text(
            "⚪ *Scan Complete:* No active Forex or Crypto setups right now.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        return

    for _, row in report.iterrows():
        msg = (
            f"{row['icon']} *{row['asset_class'].upper()} OPPORTUNITY*\n\n"
            f"• Market: *{row['asset_class']}*\n"
            f"• Symbol: *{row['symbol']}* ({row['timeframe']})\n"
            f"• Signal: *{row['action']}*\n"
            f"• Entry: `{row['entry']}`\n"
            f"• Stop Loss: `{row['stop_loss']}`\n"
            f"• Take Profit: `{row['take_profit']}`\n"
            f"• RSI: `{row['rsi']}`\n\n"
            f"💡 _Ready for execution on your broker or exchange._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⚡ Scan Market Opportunities":
        await cmd_scan(update, context)
    elif text == "ℹ️ System Status":
        await cmd_status(update, context)