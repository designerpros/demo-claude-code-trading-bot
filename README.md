# Altcoin Trading Bot

A sophisticated paper trading bot for cryptocurrency trading with technical analysis, multi-source data redundancy, and a responsive web dashboard.

## Features

- **Paper Trading**: Simulates live trading without real money (switchable to live trading)
- **Multi-Source Data**: Redundant data collection from CoinGecko, Binance, and CoinCap APIs
- **Technical Analysis**: EMA crossovers, RSI, and ATR-based signals
- **Smart Position Management**: Dynamic position sizing based on available liquidity
- **Risk Management**: Stop loss, trailing stop, and momentum-based exits
- **Real-time Dashboard**: Responsive web GUI for monitoring portfolio and trades
- **Comprehensive Logging**: All trades logged with unique IDs and full transaction history
- **Database Storage**: PostgreSQL for robust data persistence

## Architecture

### Trading Strategy

**Entry Conditions** (ALL must be met):
1. No existing position in the asset
2. Fast EMA (12) crossed above Slow EMA (48) within last 5 candles (momentum confirmation)
3. Significant price movement: |Close today - Close yesterday| > 0.2 × ATR(10) (signal strength validation)

**Exit Conditions** (ANY triggers exit):
1. 25% stop loss from entry price
2. 30% trailing stop from highest value
3. Slow EMA (48) crosses above Fast EMA (12) (bearish reversal)

### Position Sizing
- Each position: 5% of available liquidity
- No pyramiding or partial exits
- Entry fee: 0.5% of transaction value
- Exit fee: 1.0% of transaction value

### Data Collection
- **Bootstrap**: Fetches 48 daily candles directly for fast initialization (~50 seconds)
- **Ongoing**: Collects 15-minute OHLCV data every 15 minutes
- **Aggregation**: Aggregates 15m to daily candles for strategy analysis
- **Trading**: Executes trades once per day based on daily candles
- **Tracking**: Monitors top 100 assets by volume and market cap

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd demo-claude-code-trading-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup PostgreSQL Database

Create a PostgreSQL database and user:

```sql
CREATE DATABASE trading_bot;
CREATE USER trading_bot_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading_bot_user;
```

### 4. Configure Environment

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_bot
DB_USER=trading_bot_user
DB_PASSWORD=your_secure_password

# Optional API keys for better rate limits
COINGECKO_API_KEY=
BINANCE_API_KEY=
BINANCE_API_SECRET=
COINCAP_API_KEY=
```

### 5. Update Configuration

Edit `config/config.yaml` to customize trading parameters:

```yaml
portfolio:
  initial_balance: 10000.0  # Starting balance in USDT

trading:
  mode: paper  # paper or live
  position_size_percentage: 5.0
  entry_fee_percentage: 0.5
  exit_fee_percentage: 1.0

schedule:
  trading_hour: 0  # UTC hour for daily trading
  trading_minute: 5
```

## Usage

### Running the Trading Bot

```bash
python src/main.py
```

The bot will:
1. Initialize the database with schema
2. Bootstrap 48 days of historical data
3. Start scheduled tasks:
   - Data collection every 15 minutes
   - Daily candle aggregation every hour
   - Trading cycle once per day
   - Position price updates every 15 minutes

### Running the Web Dashboard

In a separate terminal:

```bash
python src/gui/app.py
```

Then open your browser to: `http://localhost:5000`

The dashboard shows:
- Portfolio summary (total value, cash, positions)
- Open positions with unrealized P&L
- Recent trades history
- Trading statistics (win rate, total P&L, etc.)

Dashboard auto-refreshes every 15 minutes.

## Project Structure

```
demo-claude-code-trading-bot/
├── config/
│   └── config.yaml           # Main configuration
├── database/
│   └── schema.sql            # Database schema
├── logs/
│   └── trading_bot.log       # Application logs
├── src/
│   ├── data/
│   │   ├── collectors.py     # Multi-source data collection
│   │   ├── aggregator.py     # 15m to daily aggregation
│   │   └── storage.py        # Database operations
│   ├── strategy/
│   │   ├── indicators.py     # Technical indicators (EMA, RSI, ATR)
│   │   ├── signals.py        # Entry/exit signal generation
│   │   └── position_manager.py  # Position tracking
│   ├── trading/
│   │   └── paper_trader.py   # Paper trading engine
│   ├── portfolio/
│   │   └── manager.py        # Portfolio & liquidity management
│   ├── reporting/
│   │   └── reporter.py       # Reporting & statistics
│   ├── gui/
│   │   ├── app.py            # Flask web app
│   │   └── templates/
│   │       └── dashboard.html  # Dashboard UI
│   └── main.py               # Main orchestrator
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## Database Schema

### Key Tables

- **assets**: Tracked cryptocurrency assets
- **ohlcv_data**: 15-minute candle data
- **daily_candles**: Aggregated daily candles
- **trades**: All trade records with unique IDs
- **positions**: Open and closed positions
- **portfolio_snapshots**: Daily portfolio state
- **indicators**: Calculated technical indicators
- **system_logs**: System event logs

## Trading Workflow

### Initial Bootstrap (One-time)
- Fetch top 100 assets by volume/market cap
- Fetch 48 daily candles per asset (1 API call each)
- Calculate technical indicators
- **Total time: ~50 seconds for 100 assets**

### Ongoing Operations

1. **Data Collection** (Every 15 minutes)
   - Fetch 15m OHLCV data from multiple sources
   - Store in database with source tracking
   - Builds granular historical database over time

2. **Aggregation** (Every hour)
   - Aggregate new 15m candles into daily candles
   - Recalculate technical indicators (EMA, RSI, ATR)
   - Update daily candle database

3. **Trading Cycle** (Once per day)
   - Update position prices
   - Generate exit signals (check stop loss, trailing stop, EMA reversal)
   - Execute exits first
   - Generate entry signals (check EMA crossover, RSI/ATR conditions)
   - Execute entries
   - Update portfolio snapshot
   - Generate reports

4. **Position Updates** (Every 15 minutes)
   - Update current prices for open positions
   - Track highest values for trailing stops

## Monitoring & Reporting

### Console Output

The bot provides colorful console output with:
- Data collection status
- Trading signals and executions
- Portfolio updates
- Position details
- Trading statistics

### Log Files

All activities logged to `logs/trading_bot.log` with timestamps and severity levels.

### Web Dashboard

Real-time monitoring with:
- Portfolio value and breakdown
- Open positions with P&L
- Recent trades
- Trading statistics
- Auto-refresh every 15 minutes

## Switching to Live Trading

⚠️ **WARNING**: Live trading involves real money and real risk. Test thoroughly in paper mode first.

To switch to live trading:

1. Update `config/config.yaml`:
   ```yaml
   trading:
     mode: live
   ```

2. Implement live trading connector in `src/trading/live_trader.py` (currently paper only)

3. Add exchange API credentials to `.env`

4. Start with small amounts and monitor closely

## Configuration Options

### Portfolio

- `initial_balance`: Starting balance in USDT
- `currency`: Base currency (USDT)

### Trading

- `mode`: `paper` or `live`
- `position_size_percentage`: Position size as % of liquidity (default: 5%)
- `entry_fee_percentage`: Entry transaction fee (default: 0.5%)
- `exit_fee_percentage`: Exit transaction fee (default: 1.0%)

### Assets

- `top_count`: Number of top assets to track (default: 100)
- `volume_priority`: Use volume as primary ranking
- `exclude_stablecoins`: Filter out stablecoins
- `tracking_threshold`: Stop tracking if rank > threshold and no position

### Indicators

- `ema_fast`: Fast EMA period (default: 12)
- `ema_slow`: Slow EMA period (default: 48)
- `rsi_period`: RSI period (default: 14)
- `rsi_oversold`: RSI oversold threshold (default: 30)
- `atr_period`: ATR period (default: 10)
- `atr_multiplier`: ATR breakout multiplier (default: 0.1)
- `crossover_lookback`: Candles to check for crossover (default: 5)

### Exit Conditions

- `stop_loss_percentage`: Stop loss from entry (default: 25%)
- `trailing_stop_percentage`: Trailing stop from peak (default: 30%)

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -h localhost -U trading_bot_user -d trading_bot
```

### API Rate Limits

The bot uses multiple data sources for redundancy. If you hit rate limits:
- Add API keys to `.env` for higher limits
- Reduce data collection frequency in config
- Bootstrap with fewer assets initially

### Missing Data

If historical data is incomplete:
```bash
# Clear and re-bootstrap
psql -h localhost -U trading_bot_user -d trading_bot -c "TRUNCATE ohlcv_data, daily_candles, indicators CASCADE;"
# Then restart the bot
```

### Performance Issues

For large datasets:
- Ensure database indexes are created (automatically done by schema.sql)
- Increase PostgreSQL shared_buffers
- Consider archiving old data

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black src/

# Check linting
flake8 src/
```

## Roadmap

- [ ] Live trading implementation
- [ ] More technical indicators (MACD, Bollinger Bands)
- [ ] Backtesting engine
- [ ] Advanced portfolio optimization
- [ ] Machine learning signal enhancement
- [ ] Mobile-responsive dashboard improvements
- [ ] Real-time WebSocket updates
- [ ] Email/SMS notifications for trades
- [ ] Multi-timeframe analysis

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies carries substantial risk. The authors are not responsible for any financial losses incurred through use of this software. Always do your own research and never invest more than you can afford to lose.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review configuration and logs

## Acknowledgments

- Technical analysis powered by pandas-ta
- Data from CoinGecko, Binance, and CoinCap APIs
- Built with Flask, PostgreSQL, and APScheduler
