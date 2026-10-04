import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import LightweightScanner

log = setup_system_logger("VIPTelegramBot")

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Check Live Market Setups")],
        [KeyboardButton("💎 VIP Channel Info"), KeyboardButton("📊 Strategy & Risk Guide")]
    ],
    resize_keyboard=True
)

def format_vip_signal(row) -> str:
    """Formats institutional-grade alerts suitable for VIP paid members."""
    is_crypto = row["asset_class"] == "CRYPTO"
    direction_badge = "🟢 LONG" if "BUY" in row["action"] else "🔴 SHORT"

    if is_crypto:
        exchange_note = "Binance Futures (USDT-M) / Bybit"
        leverage_note = "3x – 5x (Max 5x isolated recommended)"
        size_note = "1% to 2% Max Portfolio Risk"
    else:
        exchange_note = "Standard MT4 / MT5 / cTrader Broker"
        leverage_note = "1:50 to 1:200 Standard Forex"
        size_note = "0.01 lot per $500–$1,000 Equity"

    msg = (
        f"═══════════════════════════\n"
        f"💎 **VIP TRADE OPPORTUNITY** {row['icon']}\n"
        f"═══════════════════════════\n\n"
        f"• **Asset:** `{row['symbol']}`\n"
        f"• **Market:** {row['asset_class']} ({exchange_note})\n"
        f"• **Signal:** {direction_badge}\n"
        f"• **Execution:** Market Order\n"
        f"• **Time:** `{row['time']}`\n\n"
        f"🎯 **PRICE LEVELS**\n"
        f"┌ **Entry:** `{row['entry']}`\n"
        f"├ 🛑 **Stop Loss:** `{row['sl']}` (Risk: `{row['risk_pct']}%`)\n"
        f"├ 🥇 **TP1:** `{row['tp1']}`  *(R:R 1:1.0 | Close 40% & SL to Entry)*\n"
        f"├ 🥈 **TP2:** `{row['tp2']}`  *(R:R 1:1.8 | Close 30%)*\n"
        f"└ 🏆 **TP3:** `{row['tp3']}`  *(R:R 1:2.6 | Runner / Final 30%)*\n\n"
        f"⚙️ **RISK & POSITION SIZING**\n"
        f"• **Leverage:** `{leverage_note}`\n"
        f"• **Recommended Size:** `{size_note}`\n"
        f"• **Momentum (RSI 14):** `{row['rsi']}`\n\n"
        f"⚠️ _Trade with strict risk management. Never risk more than 2% per position._\n"
        f"═══════════════════════════"
    )
    return msg

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "💎 **Institutional Signal Intelligence Engine**\n\n"
        "Delivering verified, high-probability algorithmic signals for Forex and Crypto.\n\n"
        "• **Daily Average:** 2–4 verified setups\n"
        "• **Execution:** Multi-target scale-outs (TP1, TP2, TP3)\n"
        "• **Risk Standard:** Strict 1:1.8+ Average Risk-to-Reward\n\n"
        "Use the menu below to query live opportunities."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning multi-timeframe liquidity and trend structures...*", parse_mode="Markdown")

    scanner = LightweightScanner()
    report = await scanner.scan_all()

    if report.empty:
        await update.message.reply_text(
            "⚪ **No Qualified Setups Right Now**\n\n"
            "Current market conditions do not meet our multi-timeframe trend & momentum criteria. "
            "Patience protects capital — awaiting next clean breakout.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        return

    for _, row in report.iterrows():
        await update.message.reply_text(format_vip_signal(row), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = (
        "💎 **VIP MEMBERSHIP ADVANTAGES**\n\n"
        "• **Price:** $15 / month (Introductory Tier)\n"
        "• **Volume:** 2–4 selective setups per day\n"
        "• **Coverage:** Major Forex (EUR, GBP, JPY) + Crypto (BTC, ETH, SOL)\n"
        "• **Methodology:** Multi-timeframe trend filters + Volatility breakout scaling."
    )
    await update.message.reply_text(info_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guide_text = (
        "📘 **PRO TRADE EXECUTION RULES**\n\n"
        "1. **Never skip the Stop Loss:** Always set the exact SL when entering.\n"
        "2. **The TP1 Rule:** Once price hits **TP1**, close 40% of the position and immediately move Stop Loss to your Entry price. The trade is now 100% risk-free.\n"
        "3. **TP2 & TP3:** Let the remaining position ride to TP2 (close 30%) and TP3 (close final 30%).\n"
        "4. **Capital Preservation:** Never risk more than 1–2% of your account on any single trade."
    )
    await update.message.reply_text(guide_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "⚡ Check Live Market Setups":
        await cmd_scan(update, context)
    elif txt == "💎 VIP Channel Info":
        await cmd_info(update, context)
    elif txt == "📊 Strategy & Risk Guide":
        await cmd_guide(update, context)