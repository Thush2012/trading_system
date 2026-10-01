import asyncio
from core.scanner import MarketScanner

async def main():
    # Define the assets you want to monitor
    forex_watchlist = ["EURUSD", "GBPUSD", "USDJPY"]
    crypto_watchlist = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    print(f"=== Starting Multi-Asset Market Scanner (1h Timeframe) ===")
    scanner = MarketScanner(
        forex_symbols=forex_watchlist,
        crypto_symbols=crypto_watchlist,
        timeframe="1h"
    )

    try:
        report = await scanner.scan_all()
        
        # Filter columns for a clean display
        display_cols = ["asset_class", "symbol", "close", "rsi", "action"]
        valid_cols = [c for c in display_cols if c in report.columns]
        
        print("\n--- Scan Results ---")
        print(report[valid_cols].to_string(index=False))

        # Check for immediate triggers
        triggers = report[report["action"].isin(["🟢 BUY", "🔴 SELL"])]
        if not triggers.empty:
            print("\n🚨 Active Signals Detected:")
            for _, row in triggers.iterrows():
                print(f" -> {row['action']} on {row['symbol']} at {row['close']} (RSI: {row['rsi']})")
        else:
            print("\nNo trade triggers at this moment. All markets are currently NEUTRAL.")

    finally:
        await scanner.close()

if __name__ == "__main__":
    asyncio.run(main())