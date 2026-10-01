import logging
import MetaTrader5 as mt5
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import MultiTimeframeScanner
from core.mt5_connection import connect_mt5

log = setup_system_logger("TelegramBot")

# Define persistent mobile keyboard layout
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 Live Account & PnL"), KeyboardButton("⚡ Scan Opportunities")],
        [KeyboardButton("📂 Open Positions"), KeyboardButton("🚨 EMERGENCY CLOSE ALL")]
    ],
    resize_keyboard=True
)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 *Dual-Market Trading Terminal Connected*\n\n"
        "System is running 24/7 in headless mode. Use the persistent keyboard below for quick, one-tap mobile controls."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not connect_mt5():
        await update.message.reply_text("❌ *Error:* Failed to link background MT5 engine.", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
        return

    account = mt5.account_info()
    positions = mt5.positions_get()

    if account is None:
        await update.message.reply_text("⚠️ Could not read MT5 account details.", reply_markup=MAIN_KEYBOARD)
        return

    open_pnl = sum([pos.profit for pos in positions]) if positions else 0.0

    msg = (
        f"📊 *LIVE ACCOUNT STATUS*\n"
        f"• Balance: `${account.balance:,.2f}`\n"
        f"• Equity: `${account.equity:,.2f}`\n"
        f"• Free Margin: `${account.margin_free:,.2f}`\n"
        f"• Floating PnL: *{'+$' if open_pnl >= 0 else '-$'}{abs(open_pnl):,.2f}*\n"
        f"• Open Positions: `{len(positions) if positions else 0}`\n"
        f"• Leverage: `1:{account.leverage}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 background process not linked.", reply_markup=MAIN_KEYBOARD)
        return

    positions = mt5.positions_get()
    if not positions:
        await update.message.reply_text("📂 No active open positions in MT5.", reply_markup=MAIN_KEYBOARD)
        return

    msg = "📂 *ACTIVE OPEN TRADES*\n\n"
    for pos in positions:
        side = "BUY" if pos.type == 0 else "SELL"
        pnl_symbol = "+$" if pos.profit >= 0 else "-$"
        msg += (
            f"• `{pos.symbol}` ({side}) | Lots: `{pos.volume}`\n"
            f"  Entry: `{pos.price_open}` | Current: `{pos.price_current}`\n"
            f"  Floating PnL: *{pnl_symbol}{abs(pos.profit):,.2f}*\n"
            f"  Ticket: `{pos.ticket}`\n\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Scanning markets (5m, 15m, 1h with 4H Trend Bias)...*", parse_mode="Markdown")

    scanner = MultiTimeframeScanner(
        forex_symbols=Config.FOREX_WATCHLIST,
        crypto_symbols=Config.CRYPTO_WATCHLIST,
        timeframes=["5m", "15m", "1h"]
    )
    try:
        report = await scanner.scan_all()
    finally:
        await scanner.close()

    if report.empty:
        await update.message.reply_text("No scan results returned.", reply_markup=MAIN_KEYBOARD)
        return

    active = report[report["action"].isin(["🟢 BUY", "🔴 SELL"])]
    if active.empty:
        await update.message.reply_text("⚪ *Market Scan Complete:* No high-probability setups meeting ADX + 4H criteria right now.", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
        return

    msg = "⚡ *IMMEDIATE TRADE OPPORTUNITIES FOUND:*\n\n"
    for _, row in active.iterrows():
        surge = "🔥 [SURGE] " if row.get("is_sudden_surge") else ""
        msg += (
            f"{surge}*{row['symbol']}* ({row['timeframe']}) — {row['action']}\n"
            f"• Entry: `{row['entry']}`\n"
            f"• Stop Loss: `{row['stop_loss']}`\n"
            f"• Take Profit: `{row['take_profit']}`\n"
            f"• 4H Macro Bias: `{row.get('macro_bias', 'ANY')}`\n"
            f"• RSI: `{row['rsi']}` | ADX: `{row.get('adx', 'N/A')}`\n\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_closeall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 background process not linked.", reply_markup=MAIN_KEYBOARD)
        return

    positions = mt5.positions_get()
    if not positions:
        await update.message.reply_text("ℹ️ No active positions found to close.", reply_markup=MAIN_KEYBOARD)
        return

    closed_count = 0
    total_realized = 0.0

    for pos in positions:
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue

        close_price = tick.bid if pos.type == 0 else tick.ask
        order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 1001,
            "comment": "Panic Close All via Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            closed_count += 1
            total_realized += pos.profit

    pnl_tag = "+$" if total_realized >= 0 else "-$"
    await update.message.reply_text(
        f"🛑 *PANIC CLOSE EXECUTED*\n• Positions Closed: `{closed_count}`\n• Net Realized: *{pnl_tag}{abs(total_realized):,.2f}*",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )

# Text button router to handle persistent keyboard taps
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Live Account & PnL":
        await cmd_status(update, context)
    elif text == "⚡ Scan Opportunities":
        await cmd_scan(update, context)
    elif text == "📂 Open Positions":
        await cmd_positions(update, context)
    elif text == "🚨 EMERGENCY CLOSE ALL":
        await cmd_closeall(update, context)