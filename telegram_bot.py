import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("VIPTelegramBot")
global_scanner = LightweightScanner()

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Scan Live Setups")],
        [KeyboardButton("📋 VIP Subscription Info"), KeyboardButton("📖 Risk Management Rules")]
    ],
    resize_keyboard=True
)

def format_vip_signal(row) -> str:
    """Formats institutional-grade alerts with Entry Range zones."""
    is_crypto = row["asset_class"] == "CRYPTO"
    direction_badge = "🟢 LONG" if "BUY" in row["action"] else "🔴 SHORT"

    if is_crypto:
        exchange_note = "Binance USDT-M / Bybit"
        leverage_note = "3x – 5x Isolated"
        size_note = "1% – 2% Max Risk"
    else:
        exchange_note = "MT4 / MT5 Broker"
        leverage_note = "1:50 – 1:200"
        size_note = "0.01 lot per $500–$1,000 Equity"

    msg = (
        f"═══════════════════════════\n"
        f"💎 **VIP TRADE SIGNAL** {row['icon']}\n"
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
        f"⚙️ **EXECUTION GUIDELINES**\n"
        f"• **Leverage:** `{leverage_note}`\n"
        f"• **Position Sizing:** `{size_note}`\n"
        f"• **Momentum RSI:** `{row['rsi']}`\n\n"
        f"⚠️ _Enter within the Entry Zone. If price has already reached TP1, skip the trade._\n"
        f"═══════════════════════════"
    )
    return msg

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "💎 **Institutional VIP Signal Service**\n\n"
        "Algorithmic multi-timeframe signals built for consistent profitability.\n\n"
        "• **Forex Pairs:** EURUSD, GBPUSD, USDJPY\n"
        "• **Crypto Pairs:** BTCUSDT, ETHUSDT, SOLUSDT\n"
        "• **Quality Standard:** Trend-filtered 3-Tier Take Profit\n\n"
        "Use the buttons below to interact with the system."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning market liquidity and higher-timeframe structures...*", parse_mode="Markdown")

    # Manual scans bypass the 2-hour anti-spam cooldown so you can test anytime
    report = await global_scanner.scan_all(bypass_cooldown=True)

    if report.empty:
        await update.message.reply_text(
            "⚪ **No Qualified Setups Active**\n\n"
            "All assets currently fail our 1H trend alignment or momentum criteria. "
            "Patience avoids consolidation traps.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        return

    for _, row in report.iterrows():
        await update.message.reply_text(format_vip_signal(row), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_sub_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 **VIP SUBSCRIPTION PLAN**\n\n"
        "• **Fee:** $15 / month (Introductory Price)\n"
        "• **Delivery:** Direct Telegram VIP alerts with Entry Zones & 3 TPs\n"
        "• **Frequency:** 2–4 verified, high-probability setups daily\n"
        "• **Accepted Payment:** USDT (TRC20/BEP20), Binance Pay, or Card\n\n"
        "Contact `@YourTelegramHandle` to activate your VIP access."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_risk_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = (
        "📖 **VIP CAPITAL MANAGEMENT RULES**\n\n"
        "1. **Entry Rule:** Only enter if the current market price is inside the specified Entry Zone.\n"
        "2. **TP1 Trigger:** Once TP1 is achieved, lock in 40% profit and immediately move your Stop Loss to your entry price.\n"
        "3. **TP2 & TP3:** Let the remaining 60% position run toward TP2 and TP3.\n"
        "4. **Max Risk:** Never risk more than 1% to 2% of total account capital per trade."
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