class RiskManager:
    def __init__(self, risk_per_trade_pct: float = 0.01, max_daily_drawdown_pct: float = 0.03):
        """
        :param risk_per_trade_pct: Fraction of account to risk per trade (e.g. 0.01 = 1%)
        :param max_daily_drawdown_pct: Hard kill threshold (e.g. 0.03 = 3%)
        """
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_daily_drawdown_pct = max_daily_drawdown_pct

    def calculate_forex_lot_size(self, balance: float, entry_price: float, sl_price: float, pip_value_standard_lot: float = 10.0) -> float:
        """
        Calculates MT5 lot size based on pip distance.
        Formula: Lots = (Balance * Risk%) / (Pip Distance * Pip Value)
        """
        dollar_risk = balance * self.risk_per_trade_pct
        price_distance = abs(entry_price - sl_price)
        
        # 1 pip = 0.0001 for standard currency pairs (EURUSD, GBPUSD)
        pips_at_risk = price_distance / 0.0001
        if pips_at_risk <= 0:
            return 0.01  # Minimum safe fallback lot

        lot_size = dollar_risk / (pips_at_risk * pip_value_standard_lot)
        # Round down to 2 decimal places (standard micro-lot resolution)
        return max(0.01, round(lot_size, 2))

    def calculate_crypto_position_size(self, balance: float, entry_price: float, sl_price: float) -> float:
        """
        Calculates coin quantity based on stop distance.
        Formula: Qty = (Balance * Risk%) / |Entry - SL|
        """
        dollar_risk = balance * self.risk_per_trade_pct
        risk_per_unit = abs(entry_price - sl_price)
        
        if risk_per_unit <= 0:
            return 0.0

        quantity = dollar_risk / risk_per_unit
        # Return quantity rounded to 4 decimals
        return round(quantity, 4)