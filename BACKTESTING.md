# Backtesting Guide

## Overview

The backtesting module allows you to test your trading strategy on historical data to evaluate its performance before deploying real capital.

## How It Works

1. **Historical Data Collection**: Fetches daily OHLCV data for top 100 assets during the specified period
2. **Day-by-Day Replay**: Simulates trading decisions exactly as the bot would make them in real-time
3. **Performance Analysis**: Calculates comprehensive metrics including returns, Sharpe ratio, drawdown, win rate, etc.

## Usage

### Quick Start

Run backtest on 2021-2022 altseason (preset):
```bash
python run_backtest.py --preset altseason-2021
```

### Custom Date Range

Specify custom start and end dates:
```bash
python run_backtest.py --start 2021-01-01 --end 2022-05-01
```

### Save Detailed Results

Save full trade log and equity curve to JSON:
```bash
python run_backtest.py --preset altseason-2021 --output results/backtest_2021.json
```

### List Available Presets

See all predefined backtest periods:
```bash
python run_backtest.py --list-presets
```

## Available Presets

| Preset | Period | Description |
|--------|--------|-------------|
| `altseason-2021` | Jan 2021 - May 2022 | Full 2021-2022 altseason cycle |
| `bull-market-2021` | Jan 2021 - Nov 2021 | 2021 bull market peak |
| `bear-market-2022` | Jan 2022 - Dec 2022 | 2022 bear market |
| `recent-year` | Jan 2023 - Jan 2024 | 2023 full year |

## Output Metrics

### Performance Metrics
- **Total Return**: Overall percentage gain/loss
- **Total PnL**: Absolute dollar profit/loss
- **Sharpe Ratio**: Risk-adjusted return metric
- **Max Drawdown**: Largest peak-to-trough decline

### Trade Statistics
- **Total Trades**: Number of completed trades
- **Win Rate**: Percentage of profitable trades
- **Avg Win/Loss**: Average percentage gain on winners vs losers
- **Best/Worst Trade**: Largest gain and loss

### Exit Reason Breakdown
- Stop loss triggers
- Trailing stop triggers
- Bearish momentum reversals
- End of backtest closures

## Performance Expectations

The strategy is designed for **altseason deployment only** (when BTC.D falling, BTC trending up, WALCL rising).

**Expected characteristics:**
- Works best in strong bull markets
- May underperform in sideways/bear markets
- Designed to capture 100x-1000x altcoin runs
- Wide stops (25%) to avoid shakeouts during volatility
- Targets multi-month trends, not day trading

## Time Requirements

**Data Collection Time:**
- ~2-5 minutes per 100 assets (depends on API rate limits)
- Full 2021-2022 backtest: ~5-10 minutes for data fetching
- Subsequent backtests with same data: instant

**Processing Time:**
- Day-by-day simulation: ~1-2 seconds per trading day
- 365 days = ~10 minutes total processing

## Example Output

```
📊 BACKTEST RESULTS
================================================================================

Period: 2021-01-01 to 2022-05-01 (486 days)

Initial Balance: $10,000.00
Final Balance:   $45,280.00
Total Return:    +352.80%
Total PnL:       +$35,280.00

────────────────────────────────────────────────────────────────────────────────
TRADE STATISTICS
────────────────────────────────────────────────────────────────────────────────
Total Trades:    187
Winners:         68 (36.4%)
Losers:          119
Avg Win:         +145.3%
Avg Loss:        -18.2%
Best Trade:      +847.5%
Worst Trade:     -25.0%

────────────────────────────────────────────────────────────────────────────────
RISK METRICS
────────────────────────────────────────────────────────────────────────────────
Max Drawdown:    42.3%
Sharpe Ratio:    1.85

────────────────────────────────────────────────────────────────────────────────
EXIT REASONS
────────────────────────────────────────────────────────────────────────────────
Stop loss                       89 (47.6%)
Trailing stop                   45 (24.1%)
Bearish momentum reversal       42 (22.5%)
End of backtest                 11 (5.9%)
```

## Interpreting Results

### Good Signs
- ✅ Total return > 100% during bull market
- ✅ Sharpe ratio > 1.5
- ✅ Average win significantly larger than average loss
- ✅ Max drawdown < 50%

### Warning Signs
- ⚠️ Win rate < 30% (too few winners)
- ⚠️ Average win < 2x average loss (risk/reward too low)
- ⚠️ Max drawdown > 60% (too risky)
- ⚠️ Sharpe ratio < 0.5 (poor risk-adjusted returns)

### Bear Market Expectations
If you run backtest on 2022 bear market, expect:
- Negative returns (-20% to -40%)
- High stop loss triggers
- Few trailing stop wins
- This confirms strategy is **bull market only**

## Tips

1. **Test multiple periods**: Run backtests on bull, bear, and sideways markets to understand when strategy works
2. **Compare to BTC**: Did the strategy outperform just holding BTC?
3. **Check correlation**: Look at equity curve - does it match market regime?
4. **Validate assumptions**: Does 25% stop loss work, or should you tighten/widen?
5. **Parameter optimization**: Try different EMA periods, stop percentages in separate config files

## Limitations

- **Survivorship bias**: Backtest uses current top 100, not historical top 100
- **Liquidity assumptions**: Assumes you can enter/exit at daily close price
- **No slippage**: Real trading has slippage, especially on smaller altcoins
- **Perfect data**: Assumes no API failures or missing data
- **Daily resolution**: Uses daily candles, ignores intraday volatility

Despite limitations, backtesting provides valuable insights into strategy behavior and expected performance characteristics.
