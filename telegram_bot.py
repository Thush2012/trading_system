import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("MasterTelegramBot")
global_scanner = LightweightScanner()

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Scan Live Setups")],
        [KeyboardButton("ℹ️ System Health"), KeyboardButton("📖 Risk Rules")]
    ],
    resize_keyboard=True
)

def format_master_signal(row) -> str:
    """Full institutional view sent to the Master Admin."""
    is_crypto = row["asset_class"] == "CRYPTO"
    direction_badge = "🟢 LONG" if "BUY" in row["action"] else "🔴 SHORT"
    market_note = "Binance USDT-M / Bybit" if is_crypto else "Forex Broker"
    leverage_note = "3x – 5x Isolated" if is_crypto else "1:50 – 1:200"

    msg = (
        f"═══════════════════════════\n"
        f"👑 **MASTER ENGINE SIGNAL** {row['icon']}\n"
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
        f"└ 🏆 **TP3:** `{row['tp3']}`  *(Close remaining 30%)*\n\n"
        f"⚙️ **METRICS & SIZING**\n"
        f"• **Leverage:** `{leverage_note}`\n"
        f"• **Momentum RSI (14):** `{row['rsi']}`\n"
        f"═══════════════════════════"
    )
    return msg

def format_reduced_client_signal(row) -> str:
    """Reduced, high-clarity signal automatically sent to friends/clients.
    Removes TP3, indicators, and internal metadata.
    """
    is_crypto = row["asset_class"] == "CRYPTO"
    direction = "🟢 BUY / LONG" if "BUY" in row["action"] else "🔴 SELL / SHORT"
    market_tag = "CRYPTO" if is_crypto else "FOREX"
    icon = row["icon"]

    msg = (
        f"⚡ **NEW {market_tag} TRADE OPPORTUNITY** {icon}\n\n"
        f"• **Pair:** `{row['symbol']}`\n"
        f"• **Action:** {direction}\n\n"
        f"🎯 **EXECUTION LEVELS**\n"
        f"• **Entry Zone:** `{row['entry_low']}` – `{row['entry_high']}`\n"
        f"• **Stop Loss:** `{row['sl']}`\n\n"
        f"💰 **TAKE PROFIT TARGETS**\n"
        f"• 🎯 **TP 1:** `{row['tp1']}`  *(Close 50% & Set SL to Entry)*\n"
        f"• 🎯 **TP 2:** `{row['tp2']}`  *(Final Target - Close 50%)*\n\n"
        f"⚠️ _Strict Risk: Risk maximum 1% to 2% per trade._"
    )
    return msg

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "💎 **Dual Market Trade Engine Active**\n\n"
        "• Core System: Standalone Master Engine\n"
        "• Auto-Dispatch: Broadcasts reduced signals to selected client list\n"
        "• High Accuracy: 1H Trend Confirmation + Volatility Entry Zones\n\n"
        "Tap below to trigger an immediate live scan."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        "ℹ️ **ENGINE STATUS**\n"
        "• Background Poller: Active\n"
        "• Feeds: Public Yahoo/Crypto Streams (MT5 Free)\n"
        "• Target Scale-Out: TP1, TP2, TP3 Active\n"
        "• CPU / RAM Overhead: Minimal Baseline"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_risk_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = (
        "📖 **CAPITAL MANAGEMENT RULES**\n\n"
        "1. **Entry Rule:** Only take trades if current price is inside the Entry Zone.\n"
        "2. **TP1 Trigger:** When TP1 hits, take partial profit and move SL to Entry.\n"
        "3. **TP2 Trigger:** Close remaining target volume at TP2.\n"
        "4. **Max Risk:** Never risk more than 1% to 2% of total capital."
    )
    await update.message.reply_text(rules, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning market setups...*", parse_mode="Markdown")
    try:
        report = await global_scanner.scan_all(bypass_cooldown=True)
        if report.empty:
            await update.message.reply_text(
                "⚪ **No Qualified Setups Active**\n\n"
                "All pairs currently fail 1H trend alignment or momentum criteria.",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
            return

        for _, row in report.iterrows():
            await update.message.reply_text(format_master_signal(row), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        log.error(f"Error during manual scan: {e}")
        await update.message.reply_text(f"⚠️ Scan error: `{e}`", parse_mode="Markdown")

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "⚡ Scan Live Setups":
        await cmd_scan(update, context)
    elif txt == "ℹ️ System Health":
        await cmd_status(update, context)
    elif txt == "📖 Risk Rules":
        await cmd_risk_rules(update, context)