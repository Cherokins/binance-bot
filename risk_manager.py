"""
Risk Manager
- Dynamic position sizing (Kelly-inspired)
- ATR-based Stop Loss / Take Profit
- Daily loss circuit breaker
"""

import os

class RiskManager:
    MAX_RISK_PER_TRADE = 0.02    # max 2% of balance per trade
    MIN_RISK_REWARD    = 1.5     # minimum 1.5:1 R:R
    SL_ATR_MULT        = 1.5     # SL = 1.5 × ATR
    TP_ATR_MULT        = 2.5     # TP = 2.5 × ATR  → 1.67:1 R:R
    MAX_DAILY_LOSS_PCT = 0.05    # pause bot if down 5% today
    TRADE_USDT         = float(os.environ.get("TRADE_USDT", "20"))

    def __init__(self, client):
        self.client = client

    def get_position_size(self, balance: float, confidence: float) -> float:
        """
        Scale trade size with signal confidence.
        Confidence 0.6 → 1.0 maps to 60% → 100% of base size.
        Never risk more than MAX_RISK_PER_TRADE of balance.
        """
        base   = min(self.TRADE_USDT, balance * self.MAX_RISK_PER_TRADE * 10)
        scaled = base * (0.6 + 0.4 * confidence)
        return round(min(scaled, balance * 0.2), 2)   # max 20% of balance

    def get_sl_tp(self, action: str, atr_pct: float) -> tuple[float, float]:
        """Return SL and TP as decimals (e.g. 0.015 = 1.5%)."""
        sl = max(atr_pct * self.SL_ATR_MULT, 0.008)   # floor at 0.8%
        tp = max(atr_pct * self.TP_ATR_MULT, sl * self.MIN_RISK_REWARD)
        return round(sl, 4), round(tp, 4)

    def is_daily_loss_ok(self, start_balance: float, current_balance: float) -> bool:
        loss_pct = (start_balance - current_balance) / start_balance
        return loss_pct < self.MAX_DAILY_LOSS_PCT
