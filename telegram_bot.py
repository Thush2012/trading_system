import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("TelegramBot")
global_scanner = LightweightScanner()

# Admin thumb keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Scan Live Setups")],
        [KeyboardButton("📋 VIP Subscription Info"), KeyboardButton("📖 Risk Management Rules")]
    ],
    resize_keyboard=True
)

def format_vip_signal(row) -> str:
    """Master detailed signal for your private admin view."""
    is_crypto = row["asset_class"] == "CRYPTO"
    direction_badge = "🟢 LONG" if "BUY" in row["action"] else "🔴 SHORT"
    exchange_note = "Binance USDT-M / Bybit" if is_crypto else "MT4 / MT5 Broker"
    leverage_note = "3x – 5x Isolated" if is_crypto else "1:50 – 1:200"
    size_note = "1% – 2% Max Risk" if is_crypto else "0.01 lot per $500–$1,000"

    msg = (
        f"═══════════════════════════\n"
        f"👑 **MASTER ADMIN SIGNAL** {row['icon']}\n"
        f"═══════════════════════════\n\n"
        f"• **Asset:** `{row['symbol']}`\n"
        f"• **Market:** {row['asset_class']} ({exchange_note})\n"
        f"• **Direction:** {direction_badge}\n"
        f"• **Signal Time:** `{row['time']}`\n\n"
        f"🎯 **PRICE LEVELS**\n"
        f"┌ 🟢 **Entry Zone:** `{row['entry_low']}` – `{row['entry_high']}`\n"
        f"├ 🛑 **Stop Loss:** `{row['sl']}`  *(Risk: {row['risk_pct']}%)*\n"
        f"├ 🥇 **TP1:** `{row['tp1']}`  *(Close 40% & Move SL to Entry)*\n"
        f"├ 🥈 **TP2:** `{row['tp2']}`  *(Close 30%)*\n"
        f"└ 🏆 **TP3:** `{row['tp3']}`  *(Close final 30%)*\n\n"
        f"⚙️ **METRICS & SIZING**\n"
        f"• **Leverage:** `{leverage_note}`\n"
        f"• **Position Size:** `{size_note}`\n"
        f"• **Momentum RSI:** `{row['rsi']}`\n\n"
        f"═══════════════════════════"
    )
    return msg

def format_filtered_partner_signal(row) -> str:
    """Clean, high-probability filtered signal for your friend and VIP clients.
    
    Removes TP3, indicators, and internal metadata. Focuses only on 
    Entry Range, SL, TP1, and TP2.
    """
    is_crypto = row["asset_class"] == "CRYPTO"
    direction = "🟢 BUY / LONG" if "BUY" in row["action"] else "🔴 SELL / SHORT"
    market_tag = "CRYPTO" if is_crypto else "FOREX"
    icon = row["icon"]

    msg = (
        f"⚡ **NEW {market_tag} TRADE SIGNAL** {icon}\n\n"
        f"• **Pair:** `{row['symbol']}`\n"
        f"• **Action:** {direction}\n\n"
        f"🎯 **EXECUTION LEVELS**\n"
        f"• **Entry Range:** `{row['entry_low']}` – `{row['entry_high']}`\n"
        f"• **Stop Loss:** `{row['sl']}`\n\n"
        f"💰 **TAKE PROFIT TARGETS**\n"
        f"• 🎯 **TP 1:** `{row['tp1']}`  *(Close 50% & Move SL to Entry)*\n"
        f"• 🎯 **TP 2:** `{row['tp2']}`  *(Final Target: Close remaining 50%)*\n\n"
        f"⚠️ _Strict Capital Management: Risk 1% to 2% max per trade._"
    )
    return msg

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "💎 **Dual-Market Signal Terminal Active**\n\n"
        "• Dual Delivery Engine: Master Admin & Client Channel\n"
        "• Filtered Output: TP1 & TP2 with Entry Range\n"
        "• High Accuracy: 1H Trend + Volatility Filters\n\n"
        "Use the menu below to query active opportunities."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning market liquidity and higher-timeframe structures...*", parse_mode="Markdown")

    report = await global_scanner.scan_all(bypass_cooldown=True)

    if report.empty:
        await update.message.reply_text(
            "⚪ **No Qualified Setups Active**\n\n"
            "All assets currently fail 1H trend alignment or momentum criteria. "
            "Patience protects capital.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        return

    for _, row in report.iterrows():
        await update.message.reply_text(format_vip_signal(row), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_sub_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 **VIP SUBSCRIPTION PLAN**\n\n"
        "• **Fee:** $15 / month\n"
        "• **Delivery:** Streamlined alerts with Entry Zones and TP1/TP2 targets\n"
        "• **Frequency:** 2–4 verified, high-probability setups daily\n"
        "• **Payment:** USDT (TRC20/BEP20) or Binance Pay"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_risk_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = (
        "📖 **CAPITAL MANAGEMENT RULES**\n\n"
        "1. **Entry Rule:** Only enter if the market price is within the Entry Range.\n"
        "2. **TP1 Trigger:** When TP1 hits, take 50% profit and immediately move SL to your Entry price.\n"
        "3. **TP2 Trigger:** Close the remaining 50% at TP2.\n"
        "4. **Capital Preservation:** Never risk more than 1% to 2% of total balance per trade."
    )
    await update.message.reply_text(rules, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "⚡ Scan Live Setups":
        await cmd_scan(update, context)
    elif txt == "📋 VIP Subscription Info":
        await cmd_sub_info(update, context)
    elif txt == "📖 Risk Management Rules":
        await cmd_risk_rules(update, context)