import pandas as pd
import asyncio
from core.data_fetcher import UnifiedDataFetcher
from core.strategy import StrategyEngine

class MultiTimeframeScanner:
    def __init__(self, forex_symbols: list[str], crypto_symbols: list[str], timeframes: list[str] = None):
        self.forex_symbols = forex_symbols
        self.crypto_symbols = crypto_symbols
        self.timeframes = timeframes or ["5m", "15m", "1h"]
        self.fetcher = UnifiedDataFetcher()
        self.strategy = StrategyEngine()

    def _determine_macro_bias(self, df_4h: pd.DataFrame) -> str:
        if df_4h is None or len(df_4h) < 50:
            return "ANY"
        df_calc = self.strategy.calculate_indicators(df_4h)
        latest_close = df_calc["close"].iloc[-1]
        trend_ema = df_calc["ema_trend"].iloc[-1]
        if pd.isna(trend_ema):
            return "ANY"
        return "BULLISH" if latest_close >= trend_ema else "BEARISH"

    def _detect_sudden_expansion(self, df: pd.DataFrame) -> bool:
        """Flags explosive candle movement: candle range > 1.5x average ATR."""
        if len(df) < 5 or "atr" not in df.columns:
            return False
        latest = df.iloc[-1]
        candle_range = abs(latest["high"] - latest["low"])
        avg_atr = latest["atr"]
        return bool(candle_range >= (avg_atr * 1.4))

    async def scan_all(self) -> pd.DataFrame:
        results = []

        # 1. FOREX
        for symbol in self.forex_symbols:
            try:
                df_4h = self.fetcher.fetch_forex_candles(symbol, timeframe="4h", count=250)
                macro_bias = self._determine_macro_bias(df_4h)
            except Exception:
                macro_bias = "ANY"

            for tf in self.timeframes:
                try:
                    df = self.fetcher.fetch_forex_candles(symbol, timeframe=tf, count=100)
                    analyzed = self.strategy.generate_signals(df, macro_bias=macro_bias)
                    latest = analyzed.iloc[-1]
                    sudden_expansion = self._detect_sudden_expansion(analyzed)

                    results.append({
                        "asset_class": "FOREX",
                        "symbol": symbol,
                        "timeframe": tf,
                        "macro_bias": macro_bias,
                        "action": latest["action"],
                        "entry": latest["entry_price"] if not pd.isna(latest["entry_price"]) else latest["close"],
                        "stop_loss": latest["stop_loss"],
                        "take_profit": latest["take_profit"],
                        "rsi": round(latest["rsi"], 2),
                        "atr": round(latest["atr"], 5) if "atr" in latest else 0.0,
                        "is_sudden_surge": sudden_expansion
                    })
                except Exception:
                    pass

        # 2. CRYPTO
        for symbol in self.crypto_symbols:
            try:
                df_4h = await self.fetcher.fetch_crypto_candles(symbol, timeframe="4h", count=250)
                macro_bias = self._determine_macro_bias(df_4h)
            except Exception:
                macro_bias = "ANY"

            for tf in self.timeframes:
                try:
                    df = await self.fetcher.fetch_crypto_candles(symbol, timeframe=tf, count=100)
                    analyzed = self.strategy.generate_signals(df, macro_bias=macro_bias)
                    latest = analyzed.iloc[-1]
                    sudden_expansion = self._detect_sudden_expansion(analyzed)

                    results.append({
                        "asset_class": "CRYPTO",
                        "symbol": symbol,
                        "timeframe": tf,
                        "macro_bias": macro_bias,
                        "action": latest["action"],
                        "entry": latest["entry_price"] if not pd.isna(latest["entry_price"]) else latest["close"],
                        "stop_loss": latest["stop_loss"],
                        "take_profit": latest["take_profit"],
                        "rsi": round(latest["rsi"], 2),
                        "atr": round(latest["atr"], 2) if "atr" in latest else 0.0,
                        "is_sudden_surge": sudden_expansion
                    })
                except Exception:
                    pass

        return pd.DataFrame(results)

    async def close(self):
        await self.fetcher.close()