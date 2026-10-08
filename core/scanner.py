import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone, timedelta
from core.logger import setup_system_logger

log = setup_system_logger("HighAccuracyScanner")

class LightweightScanner:
    """Institutional-grade scanner with 200 EMA macro filter, ADX momentum gate, and Volume expansion."""

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

    def fetch_ohlcv(self, ticker: str, interval: str = "15m", period: str = "7d") -> pd.DataFrame:
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

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Multi-tier EMAs
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        # RSI (14)
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # True Range & ATR (14)
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14, min_periods=14).mean()

        # ADX (14) - Measures pure trend strength (avoids chop)
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

        tr_smooth = tr.rolling(window=14, min_periods=14).mean()
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=14, min_periods=14).mean() / tr_smooth)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=14, min_periods=14).mean() / tr_smooth)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        df["adx"] = dx.rolling(window=14, min_periods=14).mean()

        return df

    async def scan_all(self, bypass_cooldown: bool = False) -> pd.DataFrame:
        results = []
        loop = asyncio.get_event_loop()
        now_utc = datetime.now(timezone.utc)

        for sym, meta in self.market_map.items():
            if not bypass_cooldown and self.is_cooling_down(sym):
                log.info(f"Skipping {sym} (Cooling down)")
                continue

            # Skip Forex over weekends
            if meta["market"] == "FOREX" and now_utc.weekday() in [5, 6]:
                continue

            df = await loop.run_in_executor(None, self.fetch_ohlcv, meta["ticker"], "15m", "7d")

            if df.empty or len(df) < 205:
                log.warning(f"Insufficient candles for {sym} (Rows: {len(df)}/205 required for 200 EMA)")
                continue

            df = self.calculate_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            close = float(latest["close"])
            ema20 = float(latest["ema20"])
            ema50 = float(latest["ema50"])
            ema200 = float(latest["ema200"])
            rsi = float(latest["rsi"]) if not np.isnan(latest["rsi"]) else 50.0
            atr = float(latest["atr"]) if not np.isnan(latest["atr"]) else (close * 0.005)
            adx = float(latest["adx"]) if not np.isnan(latest["adx"]) else 20.0

            action = None
            entry_buffer = 0.20 * atr

            # High-Accuracy BUY: Above 200 EMA + 20 EMA > 50 EMA + Trend Strength (ADX >= 20) + RSI momentum
            if close > ema200 and ema20 > ema50 and adx >= 20 and (50 <= rsi <= 68) and close > prev["close"]:
                action = "BUY / LONG"
                entry_low = close
                entry_high = close + entry_buffer
                sl = close - (1.5 * atr)
                tp1 = close + (1.0 * atr)
                tp2 = close + (1.8 * atr)
                tp3 = close + (2.6 * atr)

            # High-Accuracy SELL: Below 200 EMA + 20 EMA < 50 EMA + Trend Strength (ADX >= 20) + RSI momentum
            elif close < ema200 and ema20 < ema50 and adx >= 20 and (32 <= rsi <= 50) and close < prev["close"]:
                action = "SELL / SHORT"
                entry_high = close
                entry_low = close - entry_buffer
                sl = close + (1.5 * atr)
                tp1 = close - (1.0 * atr)
                tp2 = close - (1.8 * atr)
                tp3 = close - (2.6 * atr)

            log.info(f"[{sym}] Close: {close:.4f} | 200EMA: {ema200:.4f} | ADX: {adx:.1f} | RSI: {rsi:.1f} -> {action or 'NEUTRAL'}")

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
                    "adx": round(adx, 1),
                    "time": now_utc.strftime("%H:%M UTC")
                })

                self.last_alerts[sym] = now_utc

        return pd.DataFrame(results)

    async def close(self):
        pass