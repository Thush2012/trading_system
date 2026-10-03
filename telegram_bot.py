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
        "🤖 *Multi-Market Trading Signal Terminal*\n\n"
        "• Features: Multi-target exits (TP1, TP2, TP3)\n"
        "• Crypto Setup: Ready for Binance Futures / Spot\n"
        "• Mode: Zero-Lag Lightweight Engine\n\n"
        "Tap below to check live setups."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "ℹ️ *SYSTEM HEALTH*\n"
        "• Engine: Active Standalone\n"
        "• Targets: TP1 (40%), TP2 (30%), TP3 (30%)\n"
        "• Crypto Destination: Binance USDT-M / Spot\n"
        "• Resource Load: Baseline (< 1% CPU)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

def format_signal_message(row) -> str:
    """Builds clean Telegram alert with multi-TP and broker/Binance guidance."""
    is_crypto = row["asset_class"] == "Crypto"
    
    if is_crypto:
        msg = (
            f"🪙 *BINANCE CRYPTO SIGNAL* 🚀\n\n"
            f"• Pair: *{row['binance_symbol']}* (Perpetual / Spot)\n"
            f"• Direction: *{row['action']}*\n"
            f"• Timeframe: `{row['timeframe']}`\n"
            f"• Entry Range: `{row['entry']}`\n\n"
            f"🛡 *Risk Management:*\n"
            f"• Stop Loss: `{row['stop_loss']}` (Risk: `{row['risk_pct']}%`)\n"
            f"• Recommended Leverage: `3x - 5x` (Cross/Isolated)\n"
            f"• Recommended Position: `1% - 2%` Account Risk\n\n"
            f"🎯 *Scaled Take Profit Targets:*\n"
            f"• 🥇 *TP1:* `{row['tp1']}` _(Close 40% & move SL to Entry)_\n"
            f"• 🥈 *TP2:* `{row['tp2']}` _(Close 30%)_\n"
            f"• 🏆 *TP3:* `{row['tp3']}` _(Runner / Close remaining 30%)_\n\n"
            f"📊 *Indicator:* RSI: `{row['rsi']}`"
        )
    else:
        msg = (
            f"💱 *FOREX SIGNAL* 📈\n\n"
            f"• Symbol: *{row['symbol']}* ({row['timeframe']})\n"
            f"• Direction: *{row['action']}*\n"
            f"• Entry: `{row['entry']}`\n"
            f"• Stop Loss: `{row['stop_loss']}`\n\n"
            f"🎯 *Take Profit Levels:*\n"
            f"• 🥇 *TP1:* `{row['tp1']}` _(Secure 40% & Move to BE)_\n"
            f"• 🥈 *TP2:* `{row['tp2']}` _(Take 30%)_\n"
            f"• 🏆 *TP3:* `{row['tp3']}` _(Final 30%)_\n\n"
            f"📊 *RSI:* `{row['rsi']}`"
        )
    return msg

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning Forex & Binance Crypto pairs...*", parse_mode="Markdown")

    scanner = LightweightScanner()
    report = await scanner.scan_all()

    if report.empty:
        await update.message.reply_text(
            "⚪ *Scan Complete:* No active setups meeting multi-timeframe criteria right now.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        return

    for _, row in report.iterrows():
        msg = format_signal_message(row)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⚡ Scan Market Opportunities":
        await cmd_scan(update, context)
    elif text == "ℹ️ System Status":
        await cmd_status(update, context)