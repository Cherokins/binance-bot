"""
╔══════════════════════════════════════════════════════╗
║         BINANCE SMART BOT — by Elvis             ║
║  Multi-Strategy | Risk-Managed | Firebase Logging    ║
╚══════════════════════════════════════════════════════╝
"""

import os, time, json, asyncio, logging
from datetime import datetime, timezone
from binance.client import Client
from binance.exceptions import BinanceAPIException
from strategies import SignalEngine
from risk_manager import RiskManager
from firebase_logger import FirebaseLogger

# ── Logging ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("BinanceBot")

# ── Config ────────────────────────────────────────────
API_KEY    = os.environ["BINANCE_API_KEY"]
API_SECRET = os.environ["BINANCE_SECRET_KEY"]
TESTNET    = os.environ.get("TESTNET", "true").lower() == "true"

SYMBOLS    = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
INTERVAL   = Client.KLINE_INTERVAL_5MINUTE
CANDLES    = 200          # lookback candles for indicators
TRADE_USDT = float(os.environ.get("TRADE_USDT", "20"))  # per trade

# ── Init ──────────────────────────────────────────────
client = Client(API_KEY, API_SECRET, testnet=TESTNET)
if TESTNET:
    client.API_URL = 'https://testnet.binance.vision/api'
engine   = SignalEngine()
risk_mgr = RiskManager(client)
fb       = FirebaseLogger()

# ─────────────────────────────────────────────────────
def get_klines(symbol: str) -> list:
    return client.get_klines(
        symbol=symbol,
        interval=INTERVAL,
        limit=CANDLES
    )

def get_price(symbol: str) -> float:
    return float(client.get_symbol_ticker(symbol=symbol)["price"])

def get_balance(asset="USDT") -> float:
    b = client.get_asset_balance(asset=asset)
    return float(b["free"]) if b else 0.0

def get_open_position(symbol: str) -> dict | None:
    """Check if we already hold a position for this symbol."""
    orders = client.get_open_orders(symbol=symbol)
    return orders[0] if orders else None

def calc_quantity(symbol: str, usdt_amount: float, price: float) -> float:
    """Calculate tradeable qty respecting lot size filters."""
    info = client.get_symbol_info(symbol)
    step = None
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            step = float(f["stepSize"])
            break
    qty = usdt_amount / price
    if step:
        precision = len(str(step).rstrip("0").split(".")[-1])
        qty = round(qty - (qty % step), precision)
    return qty

def place_order(symbol: str, side: str, qty: float, sl_pct: float, tp_pct: float):
    """Place market order + OCO stop-loss/take-profit."""
    try:
        order = client.order_market(symbol=symbol, side=side, quantity=qty)
        log.info(f"✅ {side} {qty} {symbol} @ market")

        price = float(order["fills"][0]["price"]) if order.get("fills") else get_price(symbol)
        
        if side == "BUY":
            sl_price = round(price * (1 - sl_pct), 2)
            tp_price = round(price * (1 + tp_pct), 2)
        else:
            sl_price = round(price * (1 + sl_pct), 2)
            tp_price = round(price * (1 - tp_pct), 2)

        trade_data = {
            "symbol":    symbol,
            "side":      side,
            "qty":       qty,
            "entry":     price,
            "sl":        sl_price,
            "tp":        tp_price,
            "time":      datetime.now(timezone.utc).isoformat(),
            "orderId":   order["orderId"],
            "testnet":   TESTNET
        }
        fb.log_trade(trade_data)
        log.info(f"📊 SL={sl_price} | TP={tp_price}")
        return order

    except BinanceAPIException as e:
        log.error(f"❌ Order failed: {e}")
        return None

# ─────────────────────────────────────────────────────
def run_bot():
    log.info("🤖 Bot cycle starting...")
    balance = get_balance("USDT")
    log.info(f"💰 USDT Balance: {balance:.2f}")

    for symbol in SYMBOLS:
        try:
            log.info(f"🔍 Analysing {symbol}...")
            klines  = get_klines(symbol)
            price   = get_price(symbol)
            signal  = engine.get_signal(klines, price)

            log.info(f"   Signal: {signal['action']} | Score: {signal['score']:.2f} | Confidence: {signal['confidence']}")

            # Skip weak signals
            if signal["action"] == "HOLD" or signal["score"] < 0.6:
                log.info(f"   ⏭ No trade for {symbol}")
                continue

            # Check existing position
            if get_open_position(symbol):
                log.info(f"   ⚠ Already in position for {symbol}, skipping")
                continue

            # Risk check
            trade_size = risk_mgr.get_position_size(balance, signal["score"])
            qty = calc_quantity(symbol, trade_size, price)
            sl, tp = risk_mgr.get_sl_tp(signal["action"], signal["atr_pct"])

            if qty <= 0:
                log.info(f"   ⚠ Qty too small for {symbol}")
                continue

            place_order(symbol, signal["action"], qty, sl, tp)
            time.sleep(0.3)  # micro-pause between symbols

        except Exception as e:
            log.error(f"   ❌ Error on {symbol}: {e}")
            continue

    # Log portfolio snapshot
    fb.log_snapshot({
        "balance": get_balance("USDT"),
        "time":    datetime.now(timezone.utc).isoformat(),
        "testnet": TESTNET
    })
    log.info("✅ Cycle complete.")

# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # Run 6 cycles in a single GitHub Actions invocation
    # = 30 minutes of active trading per trigger
    CYCLES     = int(os.environ.get("CYCLES", "6"))
    SLEEP_SECS = int(os.environ.get("SLEEP_SECS", "60"))

    for i in range(CYCLES):
        log.info(f"\n{'='*50}\n  CYCLE {i+1}/{CYCLES}\n{'='*50}")
        run_bot()
        if i < CYCLES - 1:
            log.info(f"⏳ Sleeping {SLEEP_SECS}s before next cycle...")
            time.sleep(SLEEP_SECS)
