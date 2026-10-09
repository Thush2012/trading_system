import os
import json
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
from core.logger import setup_system_logger

log = setup_system_logger("TradeTracker")

ACTIVE_FILE = os.path.join("data", "active_trades.json")
HISTORY_FILE = os.path.join("data", "trade_history.json")

class TradeTracker:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(ACTIVE_FILE):
            with open(ACTIVE_FILE, "w") as f:
                json.dump([], f)
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w") as f:
                json.dump([], f)

    def _load_trades(self, file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_trades(self, file_path, data):
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

    def register_trade(self, row: dict, ticker: str):
        """Saves a newly signaled trade for tracking."""
        trades = self._load_trades(ACTIVE_FILE)
        
        # Avoid duplicate registration for the same symbol while active
        for t in trades:
            if t["symbol"] == row["symbol"] and t["status"] == "OPEN":
                return

        new_trade = {
            "symbol": row["symbol"],
            "ticker": ticker,
            "action": row["action"],
            "entry": (row["entry_low"] + row["entry_high"]) / 2.0,
            "sl": row["sl"],
            "tp1": row["tp1"],
            "tp2": row["tp2"],
            "tp3": row["tp3"],
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "status": "OPEN",
            "opened_at": datetime.now(timezone.utc).isoformat()
        }
        trades.append(new_trade)
        self._save_trades(ACTIVE_FILE, trades)
        log.info(f"Registered new active trade tracking for {row['symbol']}")

    def evaluate_active_trades(self) -> list:
        """Checks latest price action against active trade targets and returns update events."""
        trades = self._load_trades(ACTIVE_FILE)
        if not trades:
            return []

        updates = []
        remaining_trades = []
        history = self._load_trades(HISTORY_FILE)

        for trade in trades:
            sym = trade["symbol"]
            ticker = trade["ticker"]

            try:
                df = yf.download(ticker, period="1d", interval="15m", progress=False)
                if df.empty:
                    remaining_trades.append(trade)
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                high = float(df["High"].iloc[-1])
                low = float(df["Low"].iloc[-1])
                close = float(df["Close"].iloc[-1])
            except Exception as e:
                log.error(f"Failed fetching candles for {sym}: {e}")
                remaining_trades.append(trade)
                continue

            action = trade["action"]
            is_long = "BUY" in action or "LONG" in action

            # --- LONG EVALUATION ---
            if is_long:
                # Check Stop Loss
                if low <= trade["sl"]:
                    trade["status"] = "CLOSED_SL"
                    trade["closed_at"] = datetime.now(timezone.utc).isoformat()
                    history.append(trade)
                    outcome = "BE_EXIT" if trade["tp1_hit"] else "STOP_LOSS"
                    updates.append({
                        "symbol": sym,
                        "type": outcome,
                        "msg": f"🛑 **STOP HIT: {sym}**\nPrice hit SL level `{trade['sl']}`. " +
                               ("Trade closed at Breakeven." if trade["tp1_hit"] else "Trade closed.")
                    })
                    continue

                # Check TP3
                if high >= trade["tp3"] and not trade["tp3_hit"]:
                    trade["tp1_hit"] = True
                    trade["tp2_hit"] = True
                    trade["tp3_hit"] = True
                    trade["status"] = "CLOSED_TP3"
                    trade["closed_at"] = datetime.now(timezone.utc).isoformat()
                    history.append(trade)
                    updates.append({
                        "symbol": sym,
                        "type": "TP3",
                        "msg": f"🏆 **FULL TP3 HIT: {sym}** 🎯\nPrice reached final target `{trade['tp3']}`! 100% position closed in maximum profit."
                    })
                    continue

                # Check TP2
                if high >= trade["tp2"] and not trade["tp2_hit"]:
                    trade["tp2_hit"] = True
                    updates.append({
                        "symbol": sym,
                        "type": "TP2",
                        "msg": f"🥈 **TP2 HIT: {sym}** 🔥\nPrice hit `{trade['tp2']}`! Lock in another 30% profit. Trail SL up to TP1."
                    })

                # Check TP1
                if high >= trade["tp1"] and not trade["tp1_hit"]:
                    trade["tp1_hit"] = True
                    trade["sl"] = trade["entry"]  # Move SL to breakeven
                    updates.append({
                        "symbol": sym,
                        "type": "TP1",
                        "msg": f"🥇 **TP1 HIT: {sym}** 🚀\nPrice reached `{trade['tp1']}`! Closed 40% profit.\n👉 **Stop Loss moved to Entry (`{trade['entry']:.4f}`). Trade is now 100% Risk-Free!**"
                    })

            # --- SHORT EVALUATION ---
            else:
                # Check Stop Loss
                if high >= trade["sl"]:
                    trade["status"] = "CLOSED_SL"
                    trade["closed_at"] = datetime.now(timezone.utc).isoformat()
                    history.append(trade)
                    outcome = "BE_EXIT" if trade["tp1_hit"] else "STOP_LOSS"
                    updates.append({
                        "symbol": sym,
                        "type": outcome,
                        "msg": f"🛑 **STOP HIT: {sym}**\nPrice hit SL level `{trade['sl']}`. " +
                               ("Trade closed at Breakeven." if trade["tp1_hit"] else "Trade closed.")
                    })
                    continue

                # Check TP3
                if low <= trade["tp3"] and not trade["tp3_hit"]:
                    trade["tp1_hit"] = True
                    trade["tp2_hit"] = True
                    trade["tp3_hit"] = True
                    trade["status"] = "CLOSED_TP3"
                    trade["closed_at"] = datetime.now(timezone.utc).isoformat()
                    history.append(trade)
                    updates.append({
                        "symbol": sym,
                        "type": "TP3",
                        "msg": f"🏆 **FULL TP3 HIT: {sym}** 🎯\nPrice dropped to final target `{trade['tp3']}`! 100% position closed in maximum profit."
                    })
                    continue

                # Check TP2
                if low <= trade["tp2"] and not trade["tp2_hit"]:
                    trade["tp2_hit"] = True
                    updates.append({
                        "symbol": sym,
                        "type": "TP2",
                        "msg": f"🥈 **TP2 HIT: {sym}** 🔥\nPrice hit `{trade['tp2']}`! Lock in another 30% profit. Trail SL down to TP1."
                    })

                # Check TP1
                if low <= trade["tp1"] and not trade["tp1_hit"]:
                    trade["tp1_hit"] = True
                    trade["sl"] = trade["entry"]  # Move SL to breakeven
                    updates.append({
                        "symbol": sym,
                        "type": "TP1",
                        "msg": f"🥇 **TP1 HIT: {sym}** 🚀\nPrice reached `{trade['tp1']}`! Closed 40% profit.\n👉 **Stop Loss moved to Entry (`{trade['entry']:.4f}`). Trade is now 100% Risk-Free!**"
                    })

            remaining_trades.append(trade)

        self._save_trades(ACTIVE_FILE, remaining_trades)
        self._save_trades(HISTORY_FILE, history)
        return updates