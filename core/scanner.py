import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from core.logger import setup_system_logger

log = setup_system_logger("MarketScanner")

class LightweightScanner:
    """Standalone scanner with multi-tier TP (TP1, TP2, TP3) and Binance-ready parameters."""

    FOREX_SYMBOLS = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X"
    }

    CRYPTO_SYMBOLS = {
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
        "SOLUSD": "SOL-USD"
    }

    def __init__(self):
        self.market_map = {}
        for sym, ticker in self.FOREX_SYMBOLS.items():
            self.market_map[sym] = {"ticker": ticker, "asset_class": "Forex", "icon": "💱"}
        for sym, ticker in self.CRYPTO_SYMBOLS.items():
            # Standard Binance USDT contract symbol
            binance_sym = sym.replace("USD", "USDT")
            self.market_map[sym] = {
                "ticker": ticker, 
                "asset_class": "Crypto", 
                "icon": "🪙",
                "binance_symbol": binance_sym
            }

    def fetch_ohlcv(self, ticker: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
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
            log.error(f"Failed fetching {ticker}: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

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
            df = await loop.run_in_executor(None, self.fetch_ohlcv, meta["ticker"], "15m", "5d")
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
            # Trend continuation logic
            if ema20 > ema50 and 45 <= rsi <= 65 and latest["close"] > prev["close"]:
                action = "🟢 BUY / LONG"
                sl = close - (1.5 * atr)
                tp1 = close + (1.0 * atr)   # Secure initial profits early
                tp2 = close + (1.75 * atr)  # Mid-trend scale out
                tp3 = close + (2.5 * atr)   # Final target
            elif ema20 < ema50 and 35 <= rsi <= 55 and latest["close"] < prev["close"]:
                action = "🔴 SELL / SHORT"
                sl = close + (1.5 * atr)
                tp1 = close - (1.0 * atr)
                tp2 = close - (1.75 * atr)
                tp3 = close - (2.5 * atr)

            if action != "HOLD":
                decimals = 5 if meta["asset_class"] == "Forex" else 2
                risk_pct = round(abs(close - sl) / close * 100, 2)

                results.append({
                    "symbol": sym,
                    "binance_symbol": meta.get("binance_symbol", sym),
                    "asset_class": meta["asset_class"],
                    "icon": meta["icon"],
                    "timeframe": "15m",
                    "action": action,
                    "entry": round(close, decimals),
                    "stop_loss": round(sl, decimals),
                    "tp1": round(tp1, decimals),
                    "tp2": round(tp2, decimals),
                    "tp3": round(tp3, decimals),
                    "risk_pct": risk_pct,
                    "rsi": round(rsi, 1)
                })

        return pd.DataFrame(results)

    async def close(self):
        pass