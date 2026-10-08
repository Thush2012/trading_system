import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("MasterTelegramBot")
global_scanner = LightweightScanner()

# Unified interactive keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Scan Market Opportunities")],
        [KeyboardButton("🕒 Best Trading Hours"), KeyboardButton("ℹ️ System Status")],
        [KeyboardButton("📖 Risk Rules")]
    ],
    resize_keyboard=True
)

def format_signal_message(row) -> str:
    """Formats full trade setup with timing, opportunity badges, and 3-Tier targets."""
    is_crypto = row["asset_class"] == "CRYPTO"
    direction_badge = "🟢 BUY / LONG" if "BUY" in row["action"] else "🔴 SELL / SHORT"
    market_note = "Binance USDT-M / Bybit" if is_crypto else "Forex Broker"
    leverage_note = "3x – 5x Isolated" if is_crypto else "1:50 – 1:200"

    msg = (
        f"═══════════════════════════\n"
        f"💎 **{row.get('setup_type', 'TRADE OPPORTUNITY')}** {row['icon']}\n"
        f"═══════════════════════════\n\n"
        f"• **Asset:** `{row['symbol']}`\n"
        f"• **Market:** {row['asset_class']} ({market_note})\n"
        f"• **Direction:** {direction_badge}\n"
        f"• **Session:** {row.get('session', 'Active Session')}\n"
        f"• **Expected Duration:** `{row.get('duration', 'Intraday')}`\n"
        f"• **Signal Time:** `{row['time']}`\n\n"
        f"🎯 **PRICE LEVELS**\n"
        f"┌ 🟢 **Entry Zone:** `{row['entry_low']}` – `{row['entry_high']}`\n"
        f"├ 🛑 **Stop Loss:** `{row['sl']}`  *(Risk: {row['risk_pct']}%)*\n"
        f"├ 🥇 **TP1:** `{row['tp1']}`  *(Close 40% & Move SL to Entry)*\n"
        f"├ 🥈 **TP2:** `{row['tp2']}`  *(Close 30%)*\n"
        f"└ 🏆 **TP3:** `{row['tp3']}`  *(Runner / Final 30%)*\n\n"
        f"⚙️ **METRICS & SIZING**\n"
        f"• **Leverage:** `{leverage_note}`\n"
        f"• **Trend Strength (ADX):** `{row.get('adx', 'N/A')}`\n"
        f"• **Momentum RSI:** `{row['rsi']}`\n\n"
        f"⚠️ _Strict Capital Management: Risk 1% to 2% max per trade._\n"
        f"═══════════════════════════"
    )
    return msg

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🤖 **Dual Market Trade Engine Active**\n\n"
        "• Mode: Standalone Direct Alert Terminal\n"
        "• High Accuracy: EMA 20/50/200 + ADX Gate + RSI Bands\n"
        "• Session Timing: Auto London & New York Session Detection\n"
        "• Exits: 3-Tier Take Profit (TP1, TP2, TP3)\n\n"
        "Tap the buttons below to interact."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        "ℹ️ **SYSTEM STATUS**\n"
        "• Engine: Active Standalone (Direct Terminal)\n"
        "• Scheduler: Running every 15 minutes\n"
        "• Pairs: EURUSD, GBPUSD, USDJPY, BTCUSDT, ETHUSDT, SOLUSDT\n"
        "• Dispatch Mode: Direct Admin Only (No Forwarding)\n"
        "• Cooldown: 2 Hours per Pair Anti-Spam"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_trading_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🕒 **OPTIMAL TRADING SESSIONS (UTC & LOCAL TIME)**\n\n"
        "1. **London Open (07:00 – 12:00 UTC / 12:30 – 17:30 Local):**\n"
        "   • Highest volume for EURUSD and GBPUSD.\n\n"
        "2. **London / NY Overlap (12:00 – 16:00 UTC / 17:30 – 21:30 Local):**\n"
        "   • Peak global liquidity and strongest trend follow-through.\n\n"
        "3. **US Afternoon & Crypto Prime (16:00 – 22:00 UTC):**\n"
        "   • High directional volatility for BTC, ETH, and SOL.\n\n"
        "💡 *Tip: Quick scalps trigger most reliably during the London / NY overlap.*"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_risk_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = (
        "📖 **CAPITAL MANAGEMENT RULES**\n\n"
        "1. **Entry Rule:** Only enter if market price is within the Entry Zone.\n"
        "2. **TP1 Trigger:** When TP1 hits, close 40% and move SL to Entry immediately (Trade is now Risk-Free).\n"
        "3. **TP2 & TP3:** Let the remaining 60% ride to TP2 and TP3.\n"
        "4. **Max Risk:** Never risk more than 1% to 2% of total account capital."
    )
    await update.message.reply_text(rules, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning market liquidity and higher-timeframe structures...*", parse_mode="Markdown")
    try:
        report = await global_scanner.scan_all(bypass_cooldown=True)
        if report.empty:
            await update.message.reply_text(
                "⚪ **No Qualified Setups Active**\n\n"
                "All pairs currently fail 200 EMA macro alignment or ADX momentum criteria.\n"
                "Patience protects capital.",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
            return

        for _, row in report.iterrows():
            await update.message.reply_text(format_signal_message(row), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        log.error(f"Error during manual scan: {e}")
        await update.message.reply_text(f"⚠️ Scan error: `{e}`", parse_mode="Markdown")

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes interactive custom keyboard button presses."""
    text = update.message.text.strip()
    
    if "Scan" in text:
        await cmd_scan(update, context)
    elif "Hours" in text or "Time" in text:
        await cmd_trading_hours(update, context)
    elif "Status" in text or "Health" in text:
        await cmd_status(update, context)
    elif "Risk" in text or "Rules" in text:
        await cmd_risk_rules(update, context)
    else:
        await update.message.reply_text("Please use the menu buttons below:", reply_markup=MAIN_KEYBOARD)