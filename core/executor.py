import MetaTrader5 as mt5
from core.logger import setup_system_logger
from core.mt5_connection import connect_mt5

log = setup_system_logger("Executor")

class ExecutionEngine:
    def __init__(self, magic_number: int = 1001, slippage_deviation: int = 20):
        self.magic_number = magic_number
        self.slippage_deviation = slippage_deviation

    def _determine_filling_type(self, symbol_info) -> int:
        """Dynamically matches broker's execution filling mode (IOC, FOK, or RETURN)."""
        filling_mode = symbol_info.filling_mode
        if filling_mode & mt5.ORDER_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        elif filling_mode & mt5.ORDER_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def place_forex_order(self, symbol: str, action: str, lot_size: float, sl_points: int, tp_points: int) -> dict:
        """Routes a market order directly through the headless MT5 connection."""
        if not connect_mt5():
            log.error("Execution failed: Headless MT5 link is offline.")
            return {"status": "error", "message": "MT5 connection failed"}

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            log.error(f"Execution failed: Symbol '{symbol}' not found in MT5.")
            return {"status": "error", "message": f"Symbol {symbol} not found"}

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                log.error(f"Failed to enable symbol '{symbol}' in Market Watch.")
                return {"status": "error", "message": f"Could not select {symbol}"}

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            log.error(f"Execution failed: No tick quote available for {symbol}.")
            return {"status": "error", "message": f"No tick available for {symbol}"}

        point = symbol_info.point
        order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if action.upper() == "BUY" else tick.bid

        # Calculate exact SL and TP prices based on broker point precision
        if action.upper() == "BUY":
            sl_price = round(price - (sl_points * point), symbol_info.digits) if sl_points > 0 else 0.0
            tp_price = round(price + (tp_points * point), symbol_info.digits) if tp_points > 0 else 0.0
        else:
            sl_price = round(price + (sl_points * point), symbol_info.digits) if sl_points > 0 else 0.0
            tp_price = round(price - (tp_points * point), symbol_info.digits) if tp_points > 0 else 0.0

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": self.slippage_deviation,
            "magic": self.magic_number,
            "comment": f"AutoBot {action.upper()}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._determine_filling_type(symbol_info),
        }

        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            log.error(f"Order send returned None. Error: {err}")
            return {"status": "error", "message": str(err)}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order execution rejected. Code: {result.retcode} | Comment: {result.comment}")
            return {"status": "rejected", "code": result.retcode, "message": result.comment}

        log.info(f"Order #{result.order} executed successfully on {symbol} at {result.price}")
        return {
            "status": "success",
            "order_id": result.order,
            "entry_price": result.price,
            "volume": result.volume,
            "sl": sl_price,
            "tp": tp_price
        }

    def manage_open_positions(self, symbol: str, breakeven_pips: float = 15.0, trail_distance_pips: float = 10.0) -> list[str]:
        """
        Manages open trades with two-tier protection:
        1. Moves Stop Loss to Entry Price (Break-Even) after +15 pips to neutralize downside risk.
        2. Ratchets Trailing Stop higher/lower for every +10 pips gained beyond break-even.
        """
        notes = []
        if not connect_mt5():
            return notes

        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return notes

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return notes

        point = sym_info.point
        digits = sym_info.digits
        # 1 standard pip = 10 points for 3/5 digit broker quotes
        pip_multiplier = 10 if digits in [3, 5] else 1
        be_dist = breakeven_pips * point * pip_multiplier
        trail_dist = trail_distance_pips * point * pip_multiplier

        for pos in positions:
            current_price = pos.price_current
            entry = pos.price_open
            ticket = pos.ticket
            sl = pos.sl

            # --- BUY POSITION LOGIC ---
            if pos.type == 0:
                profit_distance = current_price - entry

                # Tier 1: Move SL to Break-Even (+ 1 pip spread buffer)
                if profit_distance >= be_dist and (sl < entry or sl == 0.0):
                    new_sl = round(entry + (1.0 * point * pip_multiplier), digits)
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket,
                        "symbol": symbol,
                        "sl": new_sl,
                        "tp": pos.tp
                    }
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        notes.append(f"🛡 *BREAK-EVEN LOCKED:* `{symbol}` Stop Loss moved to `{new_sl}`. Trade is now 100% risk-free! (Ticket: `{ticket}`)")

                # Tier 2: Dynamic Trailing Stop
                elif profit_distance > be_dist:
                    ideal_sl = round(current_price - trail_dist, digits)
                    # Step up only if the new SL improves on the current SL by at least 2 pips
                    if ideal_sl > (sl + (2.0 * point * pip_multiplier)):
                        req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": ticket,
                            "symbol": symbol,
                            "sl": ideal_sl,
                            "tp": pos.tp
                        }
                        res = mt5.order_send(req)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            notes.append(f"📈 *TRAILING PROFIT LOCKED:* `{symbol}` SL raised to `{ideal_sl}` (Ticket: `{ticket}`)")

            # --- SELL POSITION LOGIC ---
            elif pos.type == 1:
                profit_distance = entry - current_price

                # Tier 1: Move SL to Break-Even (- 1 pip spread buffer)
                if profit_distance >= be_dist and (sl > entry or sl == 0.0):
                    new_sl = round(entry - (1.0 * point * pip_multiplier), digits)
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket,
                        "symbol": symbol,
                        "sl": new_sl,
                        "tp": pos.tp
                    }
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        notes.append(f"🛡 *BREAK-EVEN LOCKED:* `{symbol}` Stop Loss moved to `{new_sl}`. Trade is now 100% risk-free! (Ticket: `{ticket}`)")

                # Tier 2: Dynamic Trailing Stop
                elif profit_distance > be_dist:
                    ideal_sl = round(current_price + trail_dist, digits)
                    # Step down only if the new SL is tighter by at least 2 pips
                    if sl == 0.0 or ideal_sl < (sl - (2.0 * point * pip_multiplier)):
                        req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": ticket,
                            "symbol": symbol,
                            "sl": ideal_sl,
                            "tp": pos.tp
                        }
                        res = mt5.order_send(req)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            notes.append(f"📈 *TRAILING PROFIT LOCKED:* `{symbol}` SL lowered to `{ideal_sl}` (Ticket: `{ticket}`)")

        return notes

    async def close(self):
        """Cleanup handler when execution engine shuts down."""
        pass