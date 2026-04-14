"""
Signal Engine — Multi-Strategy Confluence System
Strategies: EMA, RSI, MACD, Bollinger Bands, Stoch RSI,
            ADX, Ichimoku, VWAP, ATR Breakout, Volume Surge
"""

import numpy as np
import pandas as pd

class SignalEngine:
    """
    Each strategy votes BUY(+1), SELL(-1), or HOLD(0).
    Votes are weighted. Final score in [-1, 1].
    Trade fires when |score| >= threshold (default 0.6).
    """

    WEIGHTS = {
        "ema_cross":      0.20,
        "rsi":            0.12,
        "macd":           0.15,
        "bollinger":      0.10,
        "stoch_rsi":      0.10,
        "adx":            0.08,
        "ichimoku":       0.10,
        "vwap":           0.08,
        "atr_breakout":   0.07,
        "volume_surge":   0.00,  # multiplier, not voter
    }

    def get_signal(self, klines: list, current_price: float) -> dict:
        df = self._to_df(klines)
        votes = {}

        votes["ema_cross"]    = self._ema_cross(df)
        votes["rsi"]          = self._rsi(df)
        votes["macd"]         = self._macd(df)
        votes["bollinger"]    = self._bollinger(df, current_price)
        votes["stoch_rsi"]    = self._stoch_rsi(df)
        votes["adx"]          = self._adx(df)
        votes["ichimoku"]     = self._ichimoku(df)
        votes["vwap"]         = self._vwap(df, current_price)
        votes["atr_breakout"] = self._atr_breakout(df)
        vol_mult              = self._volume_surge(df)

        # Weighted score
        score = sum(
            votes[k] * self.WEIGHTS[k]
            for k in votes
        )
        # Volume boosts confidence
        score *= (1 + (vol_mult - 1) * 0.3)
        score  = max(-1.0, min(1.0, score))

        # ATR for dynamic SL/TP
        atr_pct = self._atr_pct(df)

        return {
            "action":     "BUY" if score >= 0.6 else ("SELL" if score <= -0.6 else "HOLD"),
            "score":      abs(score),
            "raw_score":  score,
            "confidence": f"{abs(score)*100:.1f}%",
            "votes":      votes,
            "vol_mult":   round(vol_mult, 2),
            "atr_pct":    atr_pct,
        }

    # ─── Data Preparation ──────────────────────────────
    def _to_df(self, klines: list) -> pd.DataFrame:
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","tbav","tbqv","ignore"
        ])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        return df.reset_index(drop=True)

    # ─── Strategy 1: EMA Crossover (9/21/50) ───────────
    def _ema_cross(self, df: pd.DataFrame) -> float:
        c = df["close"]
        e9  = c.ewm(span=9,  adjust=False).mean()
        e21 = c.ewm(span=21, adjust=False).mean()
        e50 = c.ewm(span=50, adjust=False).mean()

        if e9.iloc[-1] > e21.iloc[-1] > e50.iloc[-1]:
            # Golden: fast > med > slow
            if e9.iloc[-2] <= e21.iloc[-2]:
                return 1.0   # fresh cross
            return 0.6       # continuing trend
        elif e9.iloc[-1] < e21.iloc[-1] < e50.iloc[-1]:
            if e9.iloc[-2] >= e21.iloc[-2]:
                return -1.0
            return -0.6
        return 0.0

    # ─── Strategy 2: RSI (14) ───────────────────────────
    def _rsi(self, df: pd.DataFrame, period=14) -> float:
        delta = df["close"].diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        r     = rsi.iloc[-1]

        if r < 30:   return 1.0    # oversold
        if r < 40:   return 0.5
        if r > 70:   return -1.0   # overbought
        if r > 60:   return -0.5
        return 0.0

    # ─── Strategy 3: MACD (12/26/9) ────────────────────
    def _macd(self, df: pd.DataFrame) -> float:
        c      = df["close"]
        ema12  = c.ewm(span=12, adjust=False).mean()
        ema26  = c.ewm(span=26, adjust=False).mean()
        macd   = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist   = macd - signal

        # Histogram reversal from negative to positive = BUY
        if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
            return 1.0
        if hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
            return -1.0
        if hist.iloc[-1] > 0:
            return 0.4
        if hist.iloc[-1] < 0:
            return -0.4
        return 0.0

    # ─── Strategy 4: Bollinger Bands ───────────────────
    def _bollinger(self, df: pd.DataFrame, price: float) -> float:
        c   = df["close"]
        ma  = c.rolling(20).mean()
        std = c.rolling(20).std()
        upper = ma + 2 * std
        lower = ma - 2 * std
        bw    = (upper - lower) / ma  # bandwidth

        if price <= lower.iloc[-1]:
            return 1.0     # price at lower band = bounce buy
        if price >= upper.iloc[-1]:
            return -1.0    # price at upper band = reversal sell
        # Squeeze breakout
        if bw.iloc[-1] < bw.rolling(50).mean().iloc[-1] * 0.7:
            return 0.3     # squeeze building, neutral lean
        return 0.0

    # ─── Strategy 5: Stochastic RSI ────────────────────
    def _stoch_rsi(self, df: pd.DataFrame) -> float:
        delta = df["close"].diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))

        rsi_min = rsi.rolling(14).min()
        rsi_max = rsi.rolling(14).max()
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-9) * 100

        k = stoch_rsi.rolling(3).mean()
        d = k.rolling(3).mean()

        if k.iloc[-1] < 20 and k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
            return 1.0   # K crosses above D in oversold zone
        if k.iloc[-1] > 80 and k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
            return -1.0  # K crosses below D in overbought zone
        if k.iloc[-1] < 20:
            return 0.5
        if k.iloc[-1] > 80:
            return -0.5
        return 0.0

    # ─── Strategy 6: ADX Trend Strength ────────────────
    def _adx(self, df: pd.DataFrame, period=14) -> float:
        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        tr  = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)

        dm_plus  = (high - high.shift()).clip(lower=0)
        dm_minus = (low.shift() - low).clip(lower=0)
        dm_plus  = dm_plus.where(dm_plus > dm_minus, 0)
        dm_minus = dm_minus.where(dm_minus > dm_plus, 0)

        atr  = tr.rolling(period).mean()
        di_p = 100 * dm_plus.rolling(period).mean()  / atr
        di_m = 100 * dm_minus.rolling(period).mean() / atr
        dx   = 100 * (di_p - di_m).abs() / (di_p + di_m + 1e-9)
        adx  = dx.rolling(period).mean()

        a = adx.iloc[-1]
        p = di_p.iloc[-1]
        m = di_m.iloc[-1]

        if a > 25 and p > m:   return 0.8   # strong uptrend
        if a > 25 and p < m:   return -0.8  # strong downtrend
        if a < 20:             return 0.0   # no trend = ignore
        return 0.3 if p > m else -0.3

    # ─── Strategy 7: Ichimoku Cloud ────────────────────
    def _ichimoku(self, df: pd.DataFrame) -> float:
        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        tenkan  = (high.rolling(9).max()  + low.rolling(9).min())  / 2
        kijun   = (high.rolling(26).max() + low.rolling(26).min()) / 2
        span_a  = ((tenkan + kijun) / 2).shift(26)
        span_b  = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)

        p = close.iloc[-1]
        sa = span_a.iloc[-1]
        sb = span_b.iloc[-1]

        above_cloud = p > max(sa, sb) if pd.notna(sa) and pd.notna(sb) else None
        below_cloud = p < min(sa, sb) if pd.notna(sa) and pd.notna(sb) else None
        tenkan_cross_up = (tenkan.iloc[-1] > kijun.iloc[-1] and
                           tenkan.iloc[-2] <= kijun.iloc[-2])

        if above_cloud and tenkan_cross_up:  return 1.0
        if above_cloud:                       return 0.5
        if below_cloud and not tenkan_cross_up: return -0.5
        if below_cloud:                       return -0.3
        return 0.0

    # ─── Strategy 8: VWAP ──────────────────────────────
    def _vwap(self, df: pd.DataFrame, price: float) -> float:
        typical = (df["high"] + df["low"] + df["close"]) / 3
        vwap    = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
        v       = vwap.iloc[-1]

        pct_diff = (price - v) / v
        if pct_diff < -0.005:  return 1.0    # price well below VWAP = buy
        if pct_diff < 0:       return 0.3
        if pct_diff > 0.005:   return -1.0   # price well above VWAP = sell
        if pct_diff > 0:       return -0.3
        return 0.0

    # ─── Strategy 9: ATR Breakout ──────────────────────
    def _atr_breakout(self, df: pd.DataFrame, period=14) -> float:
        high  = df["high"]
        low   = df["low"]
        close = df["close"]
        tr    = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        # Price breaks above highest high + 1 ATR = momentum breakout
        highest = high.rolling(20).max().shift(1)
        lowest  = low.rolling(20).min().shift(1)

        if close.iloc[-1] > highest.iloc[-1] + atr.iloc[-1] * 0.5:
            return 1.0
        if close.iloc[-1] < lowest.iloc[-1] - atr.iloc[-1] * 0.5:
            return -1.0
        return 0.0

    # ─── Volume Surge (multiplier) ──────────────────────
    def _volume_surge(self, df: pd.DataFrame) -> float:
        vol_avg = df["volume"].rolling(20).mean().iloc[-1]
        vol_now = df["volume"].iloc[-1]
        ratio   = vol_now / vol_avg if vol_avg > 0 else 1.0
        return min(ratio, 3.0)   # cap at 3x boost

    # ─── ATR % for SL/TP sizing ─────────────────────────
    def _atr_pct(self, df: pd.DataFrame, period=14) -> float:
        high  = df["high"]
        low   = df["low"]
        close = df["close"]
        tr    = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return atr / close.iloc[-1]
