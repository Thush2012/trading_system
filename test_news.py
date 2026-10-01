from core.news_filter import EconomicCalendarShield

shield = EconomicCalendarShield(buffer_minutes=30)
for pair in ["EURUSD", "BTC/USDT", "GBPUSD"]:
    safe, reason = shield.is_safe_to_trade(pair)
    status = "✅ SAFE" if safe else "🛑 LOCKED"
    print(f"{pair}: {status} -> {reason}")