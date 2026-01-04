"""
mt5_meanrev_safe.py

Safety-first 1-minute mean reversion bot for MetaTrader 5
Designed for demo / micro-live only

Author philosophy:
- Capital preservation > opportunity
- Skip bad trades aggressively
"""

import time
import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

# =========================
# CONFIG
# =========================
SYMBOL = "BTCUSDm"
TIMEFRAME = mt5.TIMEFRAME_M1

LOOKBACK = 120
Z_ENTER = 1.2
Z_EXIT = 0.3

RISK_PER_TRADE = 0.003
MAX_DAILY_LOSS = 0.02
MAX_LOSS_STREAK = 3

VOL_MAX = 0.004          # max allowed 1m volatility
SPREAD_MAX = 50          # points
MIN_TRADE_INTERVAL = 180 # seconds

DEVIATION = 20
MAGIC = 777001
DRY_RUN = True

TRADE_HOURS = (8, 22)

# =========================
# STATE
# =========================
last_trade_time = None
loss_streak = 0
peak_equity = None
day_start = datetime.now().date()
start_equity = None

# =========================
# UTILS
# =========================

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")

def init():
    if not mt5.initialize():
        raise RuntimeError(mt5.last_error())
    mt5.symbol_select(SYMBOL, True)

def shutdown():
    mt5.shutdown()

def account():
    info = mt5.account_info()
    return info.balance, info.equity

def rates(n):
    utc_from = datetime.now() - timedelta(minutes=n * 2)
    r = mt5.copy_rates_from(SYMBOL, TIMEFRAME, utc_from, n)
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def zscore(series):
    std = series.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return (series.iloc[-1] - series.mean()) / std

def has_position():
    pos = mt5.positions_get(symbol=SYMBOL)
    return pos if pos else None

# =========================
# SAFETY FILTERS
# =========================

def safety_check(df):
    global last_trade_time

    now = datetime.now()

    # time filter
    if not (TRADE_HOURS[0] <= now.hour <= TRADE_HOURS[1]):
        return False, "outside trade hours"

    # trade frequency
    if last_trade_time and (now - last_trade_time).seconds < MIN_TRADE_INTERVAL:
        return False, "cooldown"

    # volatility filter
    vol = df['close'].pct_change().rolling(20).std().iloc[-1]
    if vol > VOL_MAX:
        return False, "volatility too high"

    # spread filter
    tick = mt5.symbol_info_tick(SYMBOL)
    spread = tick.ask - tick.bid
    if spread > SPREAD_MAX * mt5.symbol_info(SYMBOL).point:
        return False, "spread too wide"

    return True, "ok"

# =========================
# POSITION SIZING
# =========================

def compute_lot(equity, stop_dist):
    info = mt5.symbol_info(SYMBOL)
    tick_value = info.trade_tick_value
    tick_size = info.trade_tick_size

    value_per_price = tick_value / tick_size
    risk_amount = equity * RISK_PER_TRADE

    lots = risk_amount / (stop_dist * value_per_price)
    lots = max(info.volume_min, min(info.volume_max, lots))

    step = info.volume_step
    return round(math.floor(lots / step) * step, 8)

# =========================
# EXECUTION
# =========================

def send_order(side, volume, sl, tp):
    tick = mt5.symbol_info_tick(SYMBOL)
    price = tick.ask if side == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": DEVIATION,
        "magic": MAGIC,
        "comment": "meanrev_safe",
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    if DRY_RUN:
        log(f"DRY RUN ORDER: {request}")
        return True

    result = mt5.order_send(request)
    return result.retcode == mt5.TRADE_RETCODE_DONE

# =========================
# MAIN LOOP
# =========================

def run():
    global last_trade_time, loss_streak, peak_equity, start_equity, day_start

    init()
    log("Bot started")

    while True:
        try:
            balance, equity = account()

            if start_equity is None:
                start_equity = equity
                peak_equity = equity

            # daily reset
            if datetime.now().date() != day_start:
                day_start = datetime.now().date()
                start_equity = equity
                loss_streak = 0

            # max daily loss
            if (start_equity - equity) / start_equity > MAX_DAILY_LOSS:
                log("MAX DAILY LOSS HIT → STOP")
                time.sleep(300)
                continue

            # loss streak lock
            if loss_streak >= MAX_LOSS_STREAK:
                log("LOSS STREAK LOCK")
                time.sleep(900)
                continue

            df = rates(LOOKBACK + 5)

            ok, reason = safety_check(df)
            if not ok:
                time.sleep(5)
                continue

            # detrended price
            trend = df['close'].rolling(LOOKBACK).mean()
            signal = df['close'] - trend
            z = zscore(signal.dropna())

            pos = has_position()

            # EXIT
            if pos and abs(z) <= Z_EXIT:
                log("EXIT SIGNAL")
                for p in pos:
                    send_order("sell" if p.type == 0 else "buy", p.volume, None, None)
                last_trade_time = datetime.now()

            # ENTRY
            elif not pos:
                price = df['close'].iloc[-1]
                atr = df['high'].sub(df['low']).rolling(20).mean().iloc[-1]
                stop_dist = max(atr, price * 0.001)

                if z >= Z_ENTER:
                    lots = compute_lot(equity, stop_dist)
                    send_order("sell", lots, price + stop_dist, price - stop_dist * 1.5)
                    last_trade_time = datetime.now()

                elif z <= -Z_ENTER:
                    lots = compute_lot(equity, stop_dist)
                    send_order("buy", lots, price - stop_dist, price + stop_dist * 1.5)
                    last_trade_time = datetime.now()

            time.sleep(5)

        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(10)

# =========================

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        shutdown()
        log("Bot stopped")
