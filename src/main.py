"""
Main orchestration module for the altcoin trading bot.
Coordinates data collection, signal generation, trading, and reporting.
"""

import yaml
import logging
import colorlog
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from data.storage import DatabaseStorage
from data.collectors import DataCollector
from data.aggregator import CandleAggregator
from strategy.indicators import TechnicalIndicators
from strategy.signals import SignalGenerator
from strategy.position_manager import PositionManager
from portfolio.manager import PortfolioManager
from trading.paper_trader import PaperTrader
from reporting.reporter import Reporter

# Setup colorful logging
def setup_logging(config: dict):
    """Setup colorful console logging."""
    log_format = '%(log_color)s%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))

    # Setup file logging
    file_handler = logging.FileHandler(config.get('reporting', {}).get('log_file', 'logs/trading_bot.log'))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, file_handler]
    )

    # Set library loggers to WARNING
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator."""

    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        Initialize trading bot.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        setup_logging(self.config)

        logger.info("=" * 80)
        logger.info("🚀 INITIALIZING ALTCOIN TRADING BOT")
        logger.info("=" * 80)

        # Initialize components
        self.storage = DatabaseStorage(self.config['database'])
        self.collector = DataCollector(self.config['data'])
        self.aggregator = CandleAggregator()
        self.indicators_calc = TechnicalIndicators(self.config['indicators'])
        self.signal_gen = SignalGenerator(self.config)
        self.portfolio = PortfolioManager(
            self.storage,
            self.config['portfolio']['initial_balance']
        )
        self.positions = PositionManager(self.storage)
        self.trader = PaperTrader(
            self.storage,
            self.portfolio,
            self.positions,
            self.config['trading']
        )
        self.reporter = Reporter(self.storage, self.portfolio, self.positions)

        # State
        self.tracked_assets = []
        self.is_initialized = False
        self.scheduler = BackgroundScheduler()

        logger.info("✅ All components initialized")

    def initialize(self):
        """Initialize database and bootstrap historical data."""
        logger.info("Initializing database...")

        # Initialize database schema
        schema_file = 'database/schema.sql'
        self.storage.initialize_database(schema_file)

        logger.info("✅ Database initialized")

        # Load or initialize portfolio
        self.portfolio.initialize_from_snapshot()
        self.positions.refresh_positions()

        # Bootstrap historical data
        self.bootstrap_historical_data()

        self.is_initialized = True
        logger.info("✅ Bot initialization complete")

    def bootstrap_historical_data(self):
        """Bootstrap historical data for tracked assets."""
        logger.info("Bootstrapping historical data...")

        # Get top assets
        top_count = self.config['assets']['top_count']
        exclude_stablecoins = self.config['assets']['exclude_stablecoins']

        logger.info(f"Fetching top {top_count} assets...")
        assets = self.collector.get_top_assets(top_count, exclude_stablecoins)

        if not assets:
            logger.error("Failed to fetch top assets")
            return

        # Save assets to database
        self.storage.upsert_assets(assets)
        self.tracked_assets = [a['symbol'] for a in assets]

        logger.info(f"Tracking {len(self.tracked_assets)} assets")

        # Fetch historical data
        historical_days = self.config['data']['historical_days']
        interval = self.config['data']['candle_interval']

        logger.info(f"Fetching {historical_days} days of {interval} data...")

        for symbol in self.tracked_assets[:10]:  # Start with first 10 for faster bootstrap
            try:
                logger.info(f"Fetching data for {symbol}...")

                # Fetch OHLCV data
                since = datetime.now() - timedelta(days=historical_days + 5)  # Extra buffer
                ohlcv_data = self.collector.fetch_ohlcv(symbol, interval, since)

                if ohlcv_data:
                    # Save to database
                    self.storage.insert_ohlcv_data(ohlcv_data)

                    # Aggregate to daily
                    daily_candles = self.aggregator.aggregate_to_daily(ohlcv_data, symbol)

                    if daily_candles:
                        self.storage.insert_daily_candles(daily_candles)
                        logger.info(f"✅ {symbol}: {len(ohlcv_data)} 15m candles → {len(daily_candles)} daily candles")

                        # Calculate indicators
                        indicators = self.indicators_calc.calculate_all_indicators(daily_candles, symbol)
                        if indicators:
                            self.storage.insert_indicators(indicators)
                            logger.info(f"✅ {symbol}: Calculated {len(indicators)} indicator records")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Error bootstrapping {symbol}: {e}")
                continue

        logger.info("✅ Historical data bootstrap complete")

    def collect_data(self):
        """Collect 15-minute OHLCV data for tracked assets."""
        logger.info("📊 Collecting 15-minute data...")

        # Update tracked assets list
        self.update_tracked_assets()

        # Collect data for each asset
        interval = self.config['data']['candle_interval']
        since = datetime.now() - timedelta(hours=1)  # Get last hour to ensure we have latest

        for symbol in self.tracked_assets:
            try:
                ohlcv_data = self.collector.fetch_ohlcv(symbol, interval, since, limit=10)

                if ohlcv_data:
                    self.storage.insert_ohlcv_data(ohlcv_data)
                    logger.debug(f"✅ {symbol}: {len(ohlcv_data)} candles collected")

                time.sleep(0.2)  # Rate limiting

            except Exception as e:
                logger.error(f"Error collecting data for {symbol}: {e}")
                continue

        logger.info(f"✅ Data collection complete for {len(self.tracked_assets)} assets")

    def aggregate_daily_candles(self):
        """Aggregate 15-minute data into daily candles."""
        logger.info("📈 Aggregating daily candles...")

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        for symbol in self.tracked_assets:
            try:
                # Get 15-minute data for the last week
                ohlcv_data = self.storage.get_ohlcv_data(
                    symbol,
                    datetime.combine(week_ago, datetime.min.time()),
                    datetime.combine(today, datetime.max.time())
                )

                if ohlcv_data:
                    # Aggregate to daily
                    daily_candles = self.aggregator.aggregate_to_daily(ohlcv_data, symbol)

                    if daily_candles:
                        self.storage.insert_daily_candles(daily_candles)
                        logger.debug(f"✅ {symbol}: Aggregated {len(daily_candles)} daily candles")

                        # Calculate indicators
                        # Get all daily candles for indicator calculation
                        all_daily_candles = self.storage.get_daily_candles(
                            symbol,
                            today - timedelta(days=60),
                            today
                        )

                        if len(all_daily_candles) >= 48:  # Minimum for EMA-48
                            indicators = self.indicators_calc.calculate_all_indicators(all_daily_candles, symbol)
                            if indicators:
                                self.storage.insert_indicators(indicators)

            except Exception as e:
                logger.error(f"Error aggregating {symbol}: {e}")
                continue

        logger.info("✅ Daily candle aggregation complete")

    def update_tracked_assets(self):
        """Update the list of tracked assets."""
        top_count = self.config['assets']['top_count']
        exclude_stablecoins = self.config['assets']['exclude_stablecoins']

        # Get current top assets
        new_assets = self.collector.get_top_assets(top_count, exclude_stablecoins)

        if new_assets:
            self.storage.upsert_assets(new_assets)

            # Get assets with open positions
            open_position_assets = self.positions.get_open_position_symbols()

            # Combine top assets + assets with open positions
            tracked_symbols = set(a['symbol'] for a in new_assets)
            tracked_symbols.update(open_position_assets)

            self.tracked_assets = list(tracked_symbols)

            logger.info(f"Updated tracked assets: {len(self.tracked_assets)} total "
                       f"({len(new_assets)} top + {len(open_position_assets)} with positions)")

    def run_trading_cycle(self):
        """Execute one trading cycle: generate signals and execute trades."""
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"🔄 TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # Update position prices
            self.update_position_prices()

            # Get indicators for all assets
            today = date.today()
            indicators_by_asset = {}

            for symbol in self.tracked_assets:
                indicators = self.storage.get_latest_indicators(symbol, days=60)
                if indicators:
                    indicators_by_asset[symbol] = indicators

            # Generate exit signals first (process exits before entries)
            logger.info("Checking exit signals...")
            open_positions = self.positions.get_open_positions()
            current_prices = self.get_current_prices(self.tracked_assets)

            exit_signals = self.signal_gen.generate_exit_signals(
                open_positions,
                current_prices,
                indicators_by_asset
            )

            if exit_signals:
                logger.info(f"🔔 Found {len(exit_signals)} exit signals")
                self.trader.execute_exits(exit_signals, current_prices, datetime.now())
            else:
                logger.info("No exit signals")

            # Refresh positions and portfolio after exits
            self.positions.refresh_positions()

            # Generate entry signals
            logger.info("Checking entry signals...")
            open_position_assets = self.positions.get_open_position_symbols()

            entry_signals = self.signal_gen.generate_entry_signals(
                indicators_by_asset,
                open_position_assets
            )

            if entry_signals:
                logger.info(f"🔔 Found {len(entry_signals)} entry signals")
                self.trader.execute_entries(entry_signals, current_prices, datetime.now())
            else:
                logger.info("No entry signals")

            # Refresh positions after entries
            self.positions.refresh_positions()

            # Take portfolio snapshot
            positions_summary = self.positions.get_position_summary()
            self.portfolio.take_snapshot(
                datetime.now(),
                positions_summary['total_value'],
                positions_summary['count']
            )

            # Generate reports
            self.reporter.report_portfolio_status()
            self.reporter.report_positions()

            logger.info("=" * 80)
            logger.info("✅ Trading cycle complete")
            logger.info("=" * 80)
            logger.info("")

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)

    def update_position_prices(self):
        """Update current prices for all open positions."""
        open_position_assets = self.positions.get_open_position_symbols()

        if not open_position_assets:
            return

        current_prices = self.get_current_prices(open_position_assets)
        self.positions.update_position_prices(current_prices)

    def get_current_prices(self, symbols: list) -> dict:
        """Get current prices for multiple symbols."""
        prices = {}

        for symbol in symbols:
            try:
                price = self.collector.get_latest_price(symbol)
                if price:
                    prices[symbol] = price
            except Exception as e:
                logger.warning(f"Could not get price for {symbol}: {e}")
                continue

        return prices

    def start(self):
        """Start the trading bot with scheduler."""
        if not self.is_initialized:
            self.initialize()

        logger.info("=" * 80)
        logger.info("🎯 STARTING TRADING BOT")
        logger.info("=" * 80)

        # Schedule data collection every 15 minutes
        self.scheduler.add_job(
            self.collect_data,
            IntervalTrigger(minutes=15),
            id='collect_data',
            name='Collect 15-minute data',
            max_instances=1
        )

        # Schedule daily candle aggregation every hour
        self.scheduler.add_job(
            self.aggregate_daily_candles,
            IntervalTrigger(hours=1),
            id='aggregate_daily',
            name='Aggregate daily candles',
            max_instances=1
        )

        # Schedule trading cycle once per day (at configured time)
        trading_hour = self.config['schedule']['trading_hour']
        trading_minute = self.config['schedule']['trading_minute']

        self.scheduler.add_job(
            self.run_trading_cycle,
            CronTrigger(hour=trading_hour, minute=trading_minute),
            id='trading_cycle',
            name='Daily trading cycle',
            max_instances=1
        )

        # Schedule position price updates every 15 minutes
        self.scheduler.add_job(
            self.update_position_prices,
            IntervalTrigger(minutes=15),
            id='update_prices',
            name='Update position prices',
            max_instances=1
        )

        # Start scheduler
        self.scheduler.start()

        logger.info("✅ Scheduler started")
        logger.info(f"📊 Data collection: Every 15 minutes")
        logger.info(f"📈 Daily aggregation: Every hour")
        logger.info(f"💱 Trading cycle: Daily at {trading_hour:02d}:{trading_minute:02d} UTC")
        logger.info(f"💰 Price updates: Every 15 minutes")
        logger.info("=" * 80)

        # Run initial data collection and aggregation
        logger.info("Running initial data collection...")
        self.collect_data()
        self.aggregate_daily_candles()

        # Keep the bot running
        try:
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down...")
            self.scheduler.shutdown()
            logger.info("✅ Bot stopped")


def main():
    """Main entry point."""
    bot = TradingBot('config/config.yaml')
    bot.start()


if __name__ == '__main__':
    main()
