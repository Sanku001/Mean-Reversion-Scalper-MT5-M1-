===============================
(1) README.txt (GitHub – TXT)
===============================
MT5 SAFETY-FIRST MEAN REVERSION BOT
Overview

This project is a safety-first 1-minute mean reversion trading bot developed for MetaTrader 5 (MT5).

The algorithm is designed with capital preservation as the top priority.
It avoids trading during unfavorable market regimes such as strong trends, high volatility, and poor liquidity conditions.

This bot is intended for educational purposes, demo testing, and micro-lot experimentation only.

Core Strategy

The strategy is based on short-term statistical mean reversion.

Instead of trading raw price (which is non-stationary), the algorithm uses a detrended price signal:

Signal = Price - Rolling Mean

A Z-score is computed from this detrended signal to measure how far the current price deviates from its recent equilibrium.

Entry Logic

Long position:
Enter when Z-score <= -Z_ENTER

Short position:
Enter when Z-score >= +Z_ENTER

Entry is allowed only when:

No existing position is open

Volatility is below a predefined threshold

Spread is within acceptable bounds

Trading occurs within allowed hours

Cooldown since last trade has passed

Daily loss limit is not breached

Exit Logic

Positions are closed when the Z-score reverts toward zero:

|Z-score| <= Z_EXIT

Additional exits occur through:

Volatility-based Stop Loss

Daily loss circuit breaker

Risk Management

Risk per trade is defined as a fixed percentage of account equity

Position size is calculated using real MT5 tick value and tick size

Single position only (no stacking)

Daily drawdown limit

Consecutive loss lock

Trade cooldown timer

Safety Features

Volatility filter (avoid trending regimes)

Spread filter (avoid poor execution)

Time-of-day filter

Loss streak lock

Circuit breaker on excessive drawdown

DRY_RUN mode for paper trading

Disclaimer

This software is provided for educational purposes only.
Trading CFDs and cryptocurrencies involves significant risk.
The author assumes no responsibility for any losses incurred.

Testing Recommendation

DRY_RUN → Demo Account → Micro-Lot Live
Never skip steps.
