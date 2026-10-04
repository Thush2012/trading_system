import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone
from core.logger import setup_system_logger

log = setup_system_logger("ProMarketScanner")

class LightweightScanner:
    """Institutional-grade scanner with Multi-Timeframe validation and 3-Tier TP."""

    FOREX_PAIRS = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X"
    }

    CRYPTO_PAIRS = {
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
        "SOLUSD": "SOL-USD"
    }

    def __init__(self):
        self.market_map = {}
        for sym, ticker in self.FOREX_PAIRS.items():
            self.market_map[sym] = {"ticker": ticker, "market": "FOREX", "icon": "💱", "sym": sym}
        for sym, ticker in self.CRYPTO_PAIRS.items():
            self.market_map[sym] = {
                "ticker": ticker,
                "market": "CRYPTO",
                "icon": "🪙",
                "sym": sym.replace("USD", "USDT")
            }

    def fetch_ohlcv(self, ticker: str, interval: str, period: str) -> pd.DataFrame:
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
            log.error(f"Error fetching {ticker}: {e}")
            return pd.DataFrame()

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Fast & Medium EMAs
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        # 14-period RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # 14-period ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14, min_periods=14).mean()

        return df

    async def scan_all(self) -> pd.DataFrame:
        results = []
        loop = asyncio.get_event_loop()

        for sym, meta in self.market_map.items():
            # 15m for entry, 1h for macro trend confirmation
            df_15m = await loop.run_in_executor(None, self.fetch_ohlcv, meta["ticker"], "15m", "5d")
            df_1h = await loop.run_in_executor(None, self.fetch_ohlcv, meta["ticker"], "1h", "1mo")

            if df_15m.empty or len(df_15m) < 60 or df_1h.empty or len(df_1h) < 60:
                continue

            df_15m = self.calculate_technical_indicators(df_15m)
            df_1h = self.calculate_technical_indicators(df_1h)

            latest_15m = df_15m.iloc[-1]
            prev_15m = df_15m.iloc[-2]
            latest_1h = df_1h.iloc[-1]

            close = float(latest_15m["close"])
            ema20 = float(latest_15m["ema20"])
            ema50 = float(latest_15m["ema50"])
            rsi = float(latest_15m["rsi"]) if not np.isnan(latest_15m["rsi"]) else 50.0
            atr = float(latest_15m["atr"]) if not np.isnan(latest_15m["atr"]) else (close * 0.005)

            # Macro Trend Direction
            macro_bullish = latest_1h["close"] > latest_1h["ema50"]
            macro_bearish = latest_1h["close"] < latest_1h["ema50"]

            action = None
            # High-probability Long Setup
            if macro_bullish and ema20 > ema50 and (48 <= rsi <= 64) and latest_15m["close"] > prev_15m["close"]:
                action = "BUY / LONG"
                sl = close - (1.5 * atr)
                tp1 = close + (1.0 * atr)
                tp2 = close + (1.8 * atr)
                tp3 = close + (2.6 * atr)

            # High-probability Short Setup
            elif macro_bearish and ema20 < ema50 and (36 <= rsi <= 52) and latest_15m["close"] < prev_15m["close"]:
                action = "SELL / SHORT"
                sl = close + (1.5 * atr)
                tp1 = close - (1.0 * atr)
                tp2 = close - (1.8 * atr)
                tp3 = close - (2.6 * atr)

            if action:
                decimals = 5 if meta["market"] == "FOREX" else 2
                risk_distance = abs(close - sl)
                risk_pct = round((risk_distance / close) * 100, 2)

                results.append({
                    "symbol": meta["sym"],
                    "asset_class": meta["market"],
                    "icon": meta["icon"],
                    "action": action,
                    "entry": round(close, decimals),
                    "sl": round(sl, decimals),
                    "tp1": round(tp1, decimals),
                    "tp2": round(tp2, decimals),
                    "tp3": round(tp3, decimals),
                    "risk_pct": risk_pct,
                    "rsi": round(rsi, 1),
                    "time": datetime.now(timezone.utc).strftime("%H:%M UTC")
                })

        return pd.DataFrame(results)

    async def close(self):
        pass