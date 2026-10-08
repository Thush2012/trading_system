import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("TelegramBot")
global_scanner = LightweightScanner()

# Unified keyboard matching your Telegram interface
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Scan Market Opportunities")],
        [KeyboardButton("ℹ️ System Status"), KeyboardButton("📖 Risk Rules")]
    ],
    resize_keyboard=True
)

def format_signal_message(row) -> str:
    """Formats full trade setup with Entry Range, SL, and 3-Tier TP."""
    is_crypto = row["asset_class"] == "CRYPTO"
    direction_badge = "🟢 BUY / LONG" if "BUY" in row["action"] else "🔴 SELL / SHORT"
    market_note = "Binance USDT-M / Bybit" if is_crypto else "Forex Broker"
    leverage_note = "3x – 5x Isolated" if is_crypto else "1:50 – 1:200"

    msg = (
        f"═══════════════════════════\n"
        f"💎 **TRADE OPPORTUNITY** {row['icon']}\n"
        f"═══════════════════════════\n\n"
        f"• **Asset:** `{row['symbol']}`\n"
        f"• **Market:** {row['asset_class']} ({market_note})\n"
        f"• **Direction:** {direction_badge}\n"
        f"• **Time:** `{row['time']}`\n\n"
        f"🎯 **PRICE LEVELS**\n"
        f"┌ 🟢 **Entry Zone:** `{row['entry_low']}` – `{row['entry_high']}`\n"
        f"├ 🛑 **Stop Loss:** `{row['sl']}` (Risk: `{row['risk_pct']}%`)\n"
        f"├ 🥇 **TP1:** `{row['tp1']}`  *(Close 40% & Move SL to Entry)*\n"
        f"├ 🥈 **TP2:** `{row['tp2']}`  *(Close 30%)*\n"
        f"└ 🏆 **TP3:** `{row['tp3']}`  *(Runner / Final 30%)*\n\n"
        f"⚙️ **METRICS & SIZING**\n"
        f"• **Leverage:** `{leverage_note}`\n"
        f"• **Momentum RSI (14):** `{row['rsi']}`\n\n"
        f"⚠️ _Strict Risk: Risk maximum 1% to 2% per trade._\n"
        f"═══════════════════════════"
    )
    return msg

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🤖 **Dual Market Trade Engine Active**\n\n"
        "• Mode: Standalone Direct Alert Terminal\n"
        "• Coverage: Major Forex & Binance Crypto\n"
        "• Exits: 3-Tier Take Profit (TP1, TP2, TP3)\n\n"
        "Tap below to trigger an immediate market scan."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        "ℹ️ **SYSTEM HEALTH**\n"
        "• Engine: Active Standalone\n"
        "• Scheduler: Running every 15 minutes\n"
        "• Pairs: EURUSD, GBPUSD, USDJPY, BTCUSDT, ETHUSDT, SOLUSDT\n"
        "• Dispatch: Direct Alert Mode"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_risk_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = (
        "📖 **CAPITAL MANAGEMENT RULES**\n\n"
        "1. **Entry Rule:** Only enter if market price is within the Entry Zone.\n"
        "2. **TP1 Trigger:** When TP1 hits, close 40% and move SL to Entry (Risk-Free).\n"
        "3. **TP2 & TP3:** Let the remaining position ride to TP2 and TP3.\n"
        "4. **Max Risk:** Never risk more than 1% to 2% of total account capital."
    )
    await update.message.reply_text(rules, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning market setups...*", parse_mode="Markdown")
    try:
        report = await global_scanner.scan_all(bypass_cooldown=True)
        if report.empty:
            await update.message.reply_text(
                "⚪ **No Qualified Setups Active**\n\n"
                "All pairs currently fail trend alignment or momentum criteria.",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
            return

        for _, row in report.iterrows():
            await update.message.reply_text(format_signal_message(row), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        log.error(f"Error during scan: {e}")
        await update.message.reply_text(f"⚠️ Scan error: `{e}`", parse_mode="Markdown")

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Matches both variations so old or new buttons work seamlessly
    if "Scan" in text:
        await cmd_scan(update, context)
    elif "Status" in text or "Health" in text:
        await cmd_status(update, context)
    elif "Risk" in text or "Rules" in text:
        await cmd_risk_rules(update, context)
    else:
        await update.message.reply_text(
            "Use the menu buttons below to interact:",
            reply_markup=MAIN_KEYBOARD
        )