import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone, timedelta
from core.logger import setup_system_logger

log = setup_system_logger("ProScanner")

class LightweightScanner:
    """Responsive scanner with balanced technical filters and detailed debug diagnostics."""

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
        
        self.last_alerts = {}

    def is_cooling_down(self, sym: str, cooldown_hours: float = 2.0) -> bool:
        now = datetime.now(timezone.utc)
        if sym in self.last_alerts:
            if now - self.last_alerts[sym] < timedelta(hours=cooldown_hours):
                return True
        return False

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
            log.error(f"Error fetching {ticker}: {e}")
            return pd.DataFrame()

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

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

    async def scan_all(self, bypass_cooldown: bool = False) -> pd.DataFrame:
        results = []
        loop = asyncio.get_event_loop()
        now_utc = datetime.now(timezone.utc)

        for sym, meta in self.market_map.items():
            if not bypass_cooldown and self.is_cooling_down(sym):
                log.info(f"Skipping {sym} (Cooling down)")
                continue

            # Skip Forex only during weekends
            if meta["market"] == "FOREX" and now_utc.weekday() in [5, 6]:
                continue

            df = await loop.run_in_executor(None, self.fetch_ohlcv, meta["ticker"], "15m", "5d")

            if df.empty or len(df) < 30:
                log.warning(f"Insufficient data for {sym} (rows: {len(df)})")
                continue

            df = self.calculate_technical_indicators(df)
            latest = df.iloc[-1]

            close = float(latest["close"])
            ema20 = float(latest["ema20"])
            ema50 = float(latest["ema50"])
            rsi = float(latest["rsi"]) if not np.isnan(latest["rsi"]) else 50.0
            atr = float(latest["atr"]) if not np.isnan(latest["atr"]) else (close * 0.005)

            # Balanced trend-following criteria
            action = None
            entry_buffer = 0.25 * atr

            # Bullish trend: EMA20 above EMA50, healthy RSI momentum (above 48, not overbought > 70)
            if ema20 > ema50 and 48 <= rsi <= 70:
                action = "BUY / LONG"
                entry_low = close
                entry_high = close + entry_buffer
                sl = close - (1.5 * atr)
                tp1 = close + (1.0 * atr)
                tp2 = close + (1.8 * atr)
                tp3 = close + (2.6 * atr)

            # Bearish trend: EMA20 below EMA50, healthy RSI momentum (below 52, not oversold < 30)
            elif ema20 < ema50 and 30 <= rsi <= 52:
                action = "SELL / SHORT"
                entry_high = close
                entry_low = close - entry_buffer
                sl = close + (1.5 * atr)
                tp1 = close - (1.0 * atr)
                tp2 = close - (1.8 * atr)
                tp3 = close - (2.6 * atr)

            log.info(f"[{sym}] Close: {close:.4f} | EMA20: {ema20:.4f} | EMA50: {ema50:.4f} | RSI: {rsi:.1f} -> {action or 'NEUTRAL'}")

            if action:
                decimals = 5 if meta["market"] == "FOREX" else 2
                risk_pct = round((abs(close - sl) / close) * 100, 2)

                results.append({
                    "symbol": meta["sym"],
                    "asset_class": meta["market"],
                    "icon": meta["icon"],
                    "action": action,
                    "entry_low": round(entry_low, decimals),
                    "entry_high": round(entry_high, decimals),
                    "sl": round(sl, decimals),
                    "tp1": round(tp1, decimals),
                    "tp2": round(tp2, decimals),
                    "tp3": round(tp3, decimals),
                    "risk_pct": risk_pct,
                    "rsi": round(rsi, 1),
                    "time": now_utc.strftime("%H:%M UTC")
                })

                self.last_alerts[sym] = now_utc

        return pd.DataFrame(results)

    async def close(self):
        pass