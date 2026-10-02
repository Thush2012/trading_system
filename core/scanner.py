import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from core.logger import setup_system_logger

log = setup_system_logger("MarketScanner")

class LightweightScanner:
    """Standalone scanner with embedded indicators - no external strategy dependencies."""

    SYMBOL_MAP = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
        "SOLUSD": "SOL-USD"
    }

    def __init__(self, symbols=None):
        self.symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD", "SOLUSD"]

    def fetch_ohlcv(self, symbol: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
        ticker = self.SYMBOL_MAP.get(symbol, symbol)
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if df.empty:
                return pd.DataFrame()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
            })
            return df[["open", "high", "low", "close", "volume"]].dropna()
        except Exception as e:
            log.error(f"Failed fetching {symbol}: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Computes EMA(20, 50), RSI(14), and ATR(14) using native pandas."""
        df = df.copy()
        
        # EMAs
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

        # RSI 14
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # ATR 14
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14, min_periods=14).mean()

        return df

    async def scan_all(self) -> pd.DataFrame:
        results = []
        loop = asyncio.get_event_loop()

        for sym in self.symbols:
            df = await loop.run_in_executor(None, self.fetch_ohlcv, sym, "15m", "5d")
            if df.empty or len(df) < 50:
                continue

            df = self.calculate_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            close = float(latest["close"])
            ema20 = float(latest["ema20"])
            ema50 = float(latest["ema50"])
            rsi = float(latest["rsi"]) if not np.isnan(latest["rsi"]) else 50.0
            atr = float(latest["atr"]) if not np.isnan(latest["atr"]) else (close * 0.005)

            action = "HOLD"
            # Trend continuation condition
            if ema20 > ema50 and 45 <= rsi <= 65 and latest["close"] > prev["close"]:
                action = "🟢 BUY"
                sl = close - (1.5 * atr)
                tp = close + (2.5 * atr)
            elif ema20 < ema50 and 35 <= rsi <= 55 and latest["close"] < prev["close"]:
                action = "🔴 SELL"
                sl = close + (1.5 * atr)
                tp = close - (2.5 * atr)

            if action != "HOLD":
                results.append({
                    "symbol": sym,
                    "timeframe": "15m",
                    "action": action,
                    "entry": round(close, 5),
                    "stop_loss": round(sl, 5),
                    "take_profit": round(tp, 5),
                    "rsi": round(rsi, 1),
                    "adx": "N/A"
                })

        return pd.DataFrame(results)

    async def close(self):
        pass