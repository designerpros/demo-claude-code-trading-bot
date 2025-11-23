# Current Trading Algorithm - Complete Summary

## 📊 **Overview**
Paper trading bot for top 100 altcoins using daily candle analysis with momentum and mean-reversion hybrid strategy.

---

## 🎯 **Entry Strategy** (ALL conditions must be met)

### 1. **Position Filter**
- ❌ Skip if position already exists in asset
- ✅ Only one position per asset at a time

### 2. **Momentum Signal (Primary)**
- **EMA(12) crosses above EMA(48)** within last 5 candles
- Bullish crossover indicates upward momentum
- 5-candle lookback window for flexibility

### 3. **Confirmation Signal (Either/Or)**

**Option A: Mean Reversion (Oversold)**
- RSI(14) < 30
- Asset is oversold, expecting bounce

**Option B: Breakout Momentum**
- |Close_today - Close_yesterday| > 0.1 × ATR(10)
- Significant price movement (volatility breakout)

### 📏 **Position Sizing**
- **Fixed percentage:** 5% of available liquidity per trade
- **Dynamic:** As liquidity depletes, position sizes shrink
- **No pyramiding:** One entry per asset
- **No partial exits:** All-or-nothing exit

### 💰 **Fees**
- **Entry:** 0.5% of transaction value
- **Exit:** 1.0% of transaction value
- **Total round-trip:** ~1.5% (varies with price change)

---

## 🚪 **Exit Strategy** (ANY condition triggers exit)

### 1. **Hard Stop Loss**
- **Trigger:** -25% from entry price
- **Purpose:** Limit catastrophic losses
- **Type:** Fixed, non-adjustable

### 2. **Trailing Stop Loss**
- **Trigger:** -30% from highest position value
- **Purpose:** Lock in profits, let winners run
- **Dynamic:** Tracks peak value during trade

### 3. **Momentum Reversal**
- **Trigger:** EMA(48) crosses above EMA(12)
- **Purpose:** Exit when trend reverses
- **Signal:** Bearish crossover

---

## 📈 **Current Parameters**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| **Entry Indicators** |
| EMA Fast | 12 days | Short-term trend |
| EMA Slow | 48 days | Long-term trend |
| RSI Period | 14 days | Momentum oscillator |
| RSI Oversold | < 30 | Oversold threshold |
| ATR Period | 10 days | Volatility measure |
| ATR Multiplier | 0.1 | Breakout sensitivity |
| Crossover Lookback | 5 candles | Entry timing flexibility |
| **Exit Parameters** |
| Stop Loss | -25% | Hard loss limit |
| Trailing Stop | -30% | Profit protection |
| **Position Management** |
| Position Size | 5% liquidity | Per trade allocation |
| Max Concurrent | Unlimited | Limited by liquidity |
| Entry Fee | 0.5% | Transaction cost |
| Exit Fee | 1.0% | Transaction cost |
| **Trading Frequency** |
| Signal Check | Daily | Once per day at midnight UTC |
| Price Updates | Every 15 min | For trailing stops |

---

## 🔄 **Trading Flow**

```
DAILY CYCLE (Midnight UTC):
│
├─ 1. Update all position prices
├─ 2. Check EXIT signals first
│   ├─ Stop loss (-25% from entry)?
│   ├─ Trailing stop (-30% from peak)?
│   └─ Bearish EMA crossover?
├─ 3. Execute ALL exits → Free up liquidity
├─ 4. Check ENTRY signals
│   ├─ EMA(12) crossed above EMA(48) in last 5 days?
│   └─ RSI < 30 OR price change > 0.1×ATR?
└─ 5. Execute ALL entries → Use liquidity
```

---

## ⚠️ **Current Weaknesses** (Algorithm Analysis)

### 1. **Entry Signals - Contradictory Logic**
❌ **Problem:** Requires BOTH momentum (EMA crossover) AND mean reversion (RSI oversold)
- EMA crossover = "Price trending up"
- RSI < 30 = "Price oversold, likely been falling"
- These rarely happen together!

**Example conflict:**
- If EMA(12) crosses above EMA(48), price is rising → RSI likely NOT oversold
- If RSI < 30, price has been falling → EMA crossover likely NOT bullish

**Result:** Very few entry signals generated

### 2. **Exit Stops - Too Wide**
❌ **25% stop loss:** Allows massive drawdowns
❌ **30% trailing stop:** Can give back huge gains

**Example:**
- Entry at $100
- Rises to $200 (+100%)
- Can fall back to $140 before trailing stop triggers (-30% from $200)
- Net result: +40% instead of +100%

### 3. **No Profit Target**
❌ Missing: Take profit mechanism
- Positions can run indefinitely waiting for reversal
- No way to lock in gains at predetermined levels

### 4. **Position Sizing Issues**
❌ **Fixed 5%:** Doesn't account for volatility or confidence
- High volatility assets get same size as low volatility
- Strong signals get same size as weak signals

### 5. **No Market Context**
❌ Missing: Market regime awareness
- Trades same way in bull markets and bear markets
- No volatility adjustment
- No correlation consideration

### 6. **Slow Indicators**
❌ **EMA(48):** 48-day EMA is very slow
- Misses fast-moving opportunities
- Late to detect trend changes

### 7. **Single Timeframe**
❌ **Daily only:** No confirmation from other timeframes
- Could use weekly trend as filter
- Could use 4h for timing

### 8. **No Volume Analysis**
❌ Volume ignored in entry/exit decisions
- Breakouts without volume often fail
- Volume can confirm trend strength

---

## 📊 **Expected Performance Characteristics**

**Pros:**
✅ Simple and explainable
✅ Risk-managed with stops
✅ Diversified across 100 assets
✅ Trailing stop captures some upside

**Cons:**
❌ Low entry signal frequency (contradictory conditions)
❌ High potential drawdowns (-25% per trade)
❌ Whipsaws in ranging markets (EMA crossovers)
❌ Late entries (waiting for EMA confirmation)
❌ Gives back too much profit (30% trailing stop)

**Win Rate:** Likely 30-40% (momentum + mean reversion conflict)
**Average Win:** Moderate (trailing stop limits upside)
**Average Loss:** Large (25% stop loss)
**Expectancy:** Potentially negative due to high losses and fees

---

## 🎯 **Algorithm Type Classification**

**Current Strategy:** Hybrid Momentum + Mean Reversion
- **Momentum component:** EMA crossover (trend following)
- **Mean reversion component:** RSI oversold
- **Problem:** These are opposing philosophies!

**Better approach:** Choose one or combine logically

---

## 💡 **Ready for Your Optimizations!**

I've identified the key weaknesses. What improvements would you like to implement?

Common optimization areas:
1. **Entry logic** - Resolve momentum/mean-reversion conflict
2. **Stop placement** - Tighter stops, better risk management
3. **Profit targets** - Add take-profit levels
4. **Position sizing** - Volatility-adjusted sizing
5. **Filters** - Market regime, volume, trend strength
6. **Indicators** - Faster or multi-timeframe
7. **Exit strategy** - Better profit protection

What would you like to focus on?
