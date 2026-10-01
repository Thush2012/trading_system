import logging
import asyncio
import MetaTrader5 as mt5
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from core.config import Config
from core.logger import setup_system_logger
from core.scanner import MultiTimeframeScanner
from core.mt5_connection import connect_mt5
from core.executor import ExecutionEngine

log = setup_system_logger("TelegramBot")
executor = ExecutionEngine()

# Persistent bottom thumb keyboard
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
        "• System: 24/7 Headless Engine\n"
        "• Interactive Execution: Enabled\n"
        "Tap the buttons below to interact with MT5."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 background process not linked.", reply_markup=MAIN_KEYBOARD)
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

    # Send each found opportunity with an individual Execute / Dismiss button
    for _, row in active.iterrows():
        action_word = "BUY" if "BUY" in row["action"] else "SELL"
        symbol = row["symbol"]
        entry = row["entry"]
        sl = row["stop_loss"]
        tp = row["take_profit"]

        # Encapsulate trade parameters inside callback data
        # Format: exec|SYMBOL|ACTION|SL|TP
        callback_exec = f"exec|{symbol}|{action_word}|{sl}|{tp}"
        callback_dismiss = "dismiss"

        inline_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ Execute {action_word} 0.01", callback_data=callback_exec),
                InlineKeyboardButton("❌ Dismiss", callback_data=callback_dismiss)
            ]
        ])

        msg = (
            f"⚡ *TRADE OPPORTUNITY IDENTIFIED*\n"
            f"• Symbol: *{symbol}* ({row['timeframe']})\n"
            f"• Signal: *{row['action']}*\n"
            f"• Entry: `{entry}`\n"
            f"• Stop Loss: `{sl}`\n"
            f"• Take Profit: `{tp}`\n"
            f"• Macro Bias: `{row.get('macro_bias', 'ANY')}`\n"
            f"• RSI: `{row['rsi']}` | ADX: `{row.get('adx', 'N/A')}`\n\n"
            f"_Tap below to execute directly in MT5:_"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=inline_markup)

async def handle_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles clicks on the inline Execute / Dismiss buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "dismiss":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚪ *Setup dismissed.*", parse_mode="Markdown")
        return

    if data.startswith("exec|"):
        _, symbol, action, sl_str, tp_str = data.split("|")
        sl_val = float(sl_str)
        tp_val = float(tp_str)

        if not connect_mt5():
            await query.message.reply_text("❌ *Execution Failed:* MT5 background terminal is offline.", parse_mode="Markdown")
            return

        sym_info = mt5.symbol_info(symbol)
        if not sym_info:
            await query.message.reply_text(f"❌ *Symbol Not Found:* `{symbol}` is not configured in MT5.", parse_mode="Markdown")
            return

        point = sym_info.point
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.ask if action == "BUY" else tick.bid

        # Calculate exact point distances for the executor
        sl_points = int(abs(current_price - sl_val) / point) if point else 150
        tp_points = int(abs(current_price - tp_val) / point) if point else 300

        # Execute market deal
        res = executor.place_forex_order(
            symbol=symbol,
            action=action,
            lot_size=0.01,
            sl_points=sl_points,
            tp_points=tp_points
        )

        # Clear inline buttons so the trade cannot be double-clicked
        await query.edit_message_reply_markup(reply_markup=None)

        if res.get("status") == "success":
            confirm_msg = (
                f"🚀 *ORDER EXECUTED IN MT5*\n\n"
                f"• Symbol: `{symbol}` ({action})\n"
                f"• Ticket ID: `{res.get('order_id')}`\n"
                f"• Entry Fill: `{res.get('entry_price')}`\n"
                f"• Lot Size: `{res.get('volume')}`\n"
                f"• Stop Loss: `{res.get('sl')}`\n"
                f"• Take Profit: `{res.get('tp')}`\n\n"
                f"🛡 _Break-Even & Trailing Stop monitors activated._"
            )
            await query.message.reply_text(confirm_msg, parse_mode="Markdown")
        else:
            await query.message.reply_text(f"❌ *Trade Rejected by Broker:* {res.get('message', 'Unknown error')}", parse_mode="Markdown")

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
            "comment": "Panic Close via Bot",
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