# 🤖 Binance Smart Bot

Multi-strategy, risk-managed trading bot for Binance.  
**Stack:** GitHub Actions (cron) + Firebase Realtime DB + GitHub Pages dashboard.  
**Cost:** $0.00

---

## ⚡ Strategies Used (9-signal confluence)

| # | Strategy | What it detects |
|---|----------|----------------|
| 1 | EMA 9/21/50 Crossover | Trend direction & fresh crosses |
| 2 | RSI (14) | Overbought / oversold zones |
| 3 | MACD (12/26/9) | Momentum shifts |
| 4 | Bollinger Bands | Volatility breakouts |
| 5 | Stochastic RSI | Fine-grained momentum |
| 6 | ADX (14) | Trend strength filter |
| 7 | Ichimoku Cloud | Multi-timeframe trend |
| 8 | VWAP | Intraday fair value |
| 9 | ATR Breakout | Volatility expansion entries |
| + | Volume Surge | Signal confidence multiplier |

A trade only fires when the **weighted confluence score ≥ 0.6**.

---

## 🚀 Setup (5 steps)

### 1. Fork / clone this repo (set it to Private)

### 2. Add GitHub Secrets
Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `BINANCE_API_KEY` | Your Binance API key |
| `BINANCE_SECRET_KEY` | Your Binance secret key |
| `FIREBASE_URL` | `https://YOUR_PROJECT-default-rtdb.firebaseio.com` |
| `TESTNET` | `true` (change to `false` for live trading) |
| `TRADE_USDT` | `20` (USDT per trade) |

### 3. Enable GitHub Pages
Go to **Settings → Pages → Source: Deploy from branch → main → /dashboard**

### 4. Trigger the bot manually first
Go to **Actions → Binance Trading Bot → Run workflow**  
Check the logs to confirm it connects and scans symbols.

### 5. Let the cron run
The bot runs automatically every **30 minutes** via GitHub Actions cron.  
Each run executes **6 cycles × 60s = ~6 minutes** of active trading.

---

## 💰 Risk Management

- Max **2% of balance** risked per trade
- Stop Loss: **1.5× ATR** below entry
- Take Profit: **2.5× ATR** above entry (≥1.67:1 R:R)
- Daily loss circuit breaker: bot pauses if down **5%** in a day
- Position size scales with signal confidence

---

## 📊 Dashboard

Open your GitHub Pages URL:  
`https://YOUR_USERNAME.github.io/binance-bot/dashboard/`

Paste your Firebase Realtime DB URL → click Connect → live trade history loads.

---

## 🔁 Going Live (when ready)

Change one GitHub secret:
```
TESTNET → false
```

That's it. The same bot, same strategies, same risk rules — but real orders.

---

## 📁 File Structure

```
binance-bot/
├── bot.py              ← main orchestrator
├── strategies.py       ← all 9 signal strategies
├── risk_manager.py     ← position sizing & SL/TP
├── firebase_logger.py  ← trade logging to Firebase
├── requirements.txt
├── dashboard/
│   └── index.html      ← live dashboard (GitHub Pages)
└── .github/
    └── workflows/
        └── bot.yml     ← cron scheduler
```

---

> ⚠️ **Disclaimer:** This bot is for educational and personal use. Crypto trading carries significant risk. Always test thoroughly on testnet before using real funds.
