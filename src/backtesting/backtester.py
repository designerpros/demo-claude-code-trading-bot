"""
Backtesting engine for testing trading strategies on historical data.
Replays strategy day-by-day on historical OHLCV data.
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from collections import defaultdict
import pandas as pd
import numpy as np

from data.collectors import DataCollector
from strategy.indicators import TechnicalIndicators
from strategy.signals import SignalGenerator

logger = logging.getLogger(__name__)


class BacktestPosition:
    """Represents a position during backtesting."""

    def __init__(self, asset: str, entry_date: date, entry_price: float,
                 units: float, cost_basis: float):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.units = units
        self.cost_basis = cost_basis  # Including entry fee
        self.highest_value = cost_basis
        self.exit_date = None
        self.exit_price = None
        self.exit_value = None
        self.exit_reason = None
        self.pnl = None
        self.pnl_pct = None


class Backtester:
    """Backtests trading strategies on historical data."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize backtester.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.collector = DataCollector(config['data'])
        self.indicators_calc = TechnicalIndicators(config['indicators'])
        self.signal_gen = SignalGenerator(config)

        # Trading parameters
        self.initial_balance = config['portfolio']['initial_balance']
        self.position_size_pct = config['trading']['position_size_percentage']
        self.entry_fee_pct = config['trading']['entry_fee_percentage']
        self.exit_fee_pct = config['trading']['exit_fee_percentage']

        # Strategy parameters
        self.stop_loss_pct = config['strategy']['stop_loss_percentage']
        self.trailing_stop_pct = config['strategy']['trailing_stop_percentage']

        # State
        self.cash = Decimal(str(self.initial_balance))
        self.positions: Dict[str, BacktestPosition] = {}
        self.closed_trades: List[BacktestPosition] = []
        self.equity_curve: List[Dict] = []
        self.daily_returns: List[float] = []

    def run_backtest(self, start_date: date, end_date: date,
                     assets: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run backtest for specified date range.

        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            assets: List of assets to trade (if None, uses top 100)

        Returns:
            Dictionary with backtest results and performance metrics
        """
        logger.info("=" * 80)
        logger.info(f"🔬 STARTING BACKTEST: {start_date} to {end_date}")
        logger.info("=" * 80)

        # Get assets to trade
        if assets is None:
            logger.info("Fetching top 100 assets for backtest period...")
            assets_data = self.collector.get_top_assets(100, exclude_stablecoins=True)
            assets = [a['symbol'] for a in assets_data]

        logger.info(f"Backtesting on {len(assets)} assets")

        # Fetch historical data for all assets
        logger.info("Fetching historical data...")
        historical_data = self._fetch_historical_data(assets, start_date, end_date)

        if not historical_data:
            logger.error("Failed to fetch historical data")
            return {}

        # Get all trading dates
        all_dates = sorted(set(
            candle['date']
            for asset_data in historical_data.values()
            for candle in asset_data
        ))

        trading_dates = [d for d in all_dates if start_date <= d <= end_date]
        logger.info(f"Backtesting {len(trading_dates)} trading days")

        # Run day-by-day simulation
        for current_date in trading_dates:
            self._simulate_trading_day(current_date, historical_data)

        # Close all remaining positions at end date
        self._close_all_positions(end_date, historical_data)

        # Calculate performance metrics
        results = self._calculate_performance_metrics(start_date, end_date)

        logger.info("=" * 80)
        logger.info("✅ BACKTEST COMPLETE")
        logger.info("=" * 80)

        return results

    def _fetch_historical_data(self, assets: List[str], start_date: date,
                               end_date: date) -> Dict[str, List[Dict]]:
        """Fetch historical daily OHLCV data for all assets."""
        # Add buffer for indicator calculation (need 48 days before start)
        buffer_start = start_date - timedelta(days=60)

        historical_data = {}

        for i, symbol in enumerate(assets, 1):
            try:
                logger.info(f"[{i}/{len(assets)}] Fetching {symbol}...")

                # Fetch daily candles
                since = datetime.combine(buffer_start, datetime.min.time())
                days_needed = (end_date - buffer_start).days + 10

                daily_ohlcv = self.collector.fetch_ohlcv(
                    symbol, '1d', since, limit=days_needed
                )

                if daily_ohlcv:
                    # Convert to our format
                    candles = []
                    for candle in daily_ohlcv:
                        candles.append({
                            'date': candle['timestamp'].date(),
                            'asset': symbol,
                            'open': candle['open'],
                            'high': candle['high'],
                            'low': candle['low'],
                            'close': candle['close'],
                            'volume': candle['volume']
                        })

                    if candles:
                        historical_data[symbol] = sorted(candles, key=lambda x: x['date'])
                        logger.debug(f"✅ {symbol}: {len(candles)} candles")

                # Rate limiting
                if i % 10 == 0:
                    import time
                    time.sleep(1)

            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                continue

        logger.info(f"Successfully fetched data for {len(historical_data)} assets")
        return historical_data

    def _simulate_trading_day(self, current_date: date,
                              historical_data: Dict[str, List[Dict]]):
        """Simulate one trading day."""
        # Get current prices
        current_prices = {}
        for asset, candles in historical_data.items():
            for candle in candles:
                if candle['date'] == current_date:
                    current_prices[asset] = candle['close']
                    break

        if not current_prices:
            return

        # Check exit conditions for existing positions
        self._check_exits(current_date, current_prices, historical_data)

        # Calculate indicators for assets with enough history
        indicators_by_asset = {}
        for asset, candles in historical_data.items():
            # Get candles up to current date
            historical_candles = [c for c in candles if c['date'] <= current_date]

            if len(historical_candles) >= 48:  # Need 48 days for EMA(48)
                indicators = self.indicators_calc.calculate_all_indicators(
                    historical_candles, asset
                )
                if indicators:
                    indicators_by_asset[asset] = indicators

        # Generate entry signals
        open_positions = list(self.positions.keys())
        entry_signals = self.signal_gen.generate_entry_signals(
            indicators_by_asset, open_positions
        )

        # Execute entry trades
        for asset in entry_signals:
            if asset in current_prices:
                self._open_position(asset, current_prices[asset], current_date)

        # Record equity curve
        portfolio_value = self._calculate_portfolio_value(current_prices)
        self.equity_curve.append({
            'date': current_date,
            'cash': float(self.cash),
            'positions_value': portfolio_value - float(self.cash),
            'total_value': portfolio_value,
            'num_positions': len(self.positions)
        })

        # Calculate daily return
        if len(self.equity_curve) > 1:
            prev_value = self.equity_curve[-2]['total_value']
            daily_return = (portfolio_value - prev_value) / prev_value
            self.daily_returns.append(daily_return)

    def _check_exits(self, current_date: date, current_prices: Dict[str, float],
                     historical_data: Dict[str, List[Dict]]):
        """Check exit conditions for all open positions."""
        assets_to_close = []

        for asset, position in self.positions.items():
            if asset not in current_prices:
                continue

            current_price = current_prices[asset]
            current_value = position.units * current_price

            # Update highest value for trailing stop
            if current_value > position.highest_value:
                position.highest_value = current_value

            # Check stop loss (25% from entry)
            loss_pct = (current_price - position.entry_price) / position.entry_price
            if loss_pct <= -self.stop_loss_pct / 100.0:
                assets_to_close.append((asset, current_price, "Stop loss"))
                continue

            # Check trailing stop (30% from highest)
            trailing_loss = (current_value - position.highest_value) / position.highest_value
            if trailing_loss <= -self.trailing_stop_pct / 100.0:
                assets_to_close.append((asset, current_price, "Trailing stop"))
                continue

            # Check bearish reversal signal
            if asset in historical_data:
                candles = [c for c in historical_data[asset] if c['date'] <= current_date]
                if len(candles) >= 48:
                    indicators = self.indicators_calc.calculate_all_indicators(candles, asset)
                    if indicators and self.signal_gen._check_bearish_crossover_with_strength(indicators):
                        assets_to_close.append((asset, current_price, "Bearish momentum reversal"))
                        continue

        # Close positions
        for asset, exit_price, exit_reason in assets_to_close:
            self._close_position(asset, exit_price, current_date, exit_reason)

    def _open_position(self, asset: str, price: float, entry_date: date):
        """Open a new position."""
        # Calculate position size (X% of available cash)
        position_value = float(self.cash) * (self.position_size_pct / 100.0)
        units = position_value / price

        # Calculate fees
        entry_fee = position_value * (self.entry_fee_pct / 100.0)
        total_cost = position_value + entry_fee

        # Check if we have enough cash
        if Decimal(str(total_cost)) > self.cash:
            return

        # Deduct cash
        self.cash -= Decimal(str(total_cost))

        # Create position
        position = BacktestPosition(
            asset=asset,
            entry_date=entry_date,
            entry_price=price,
            units=units,
            cost_basis=total_cost
        )

        self.positions[asset] = position

        logger.debug(
            f"ENTRY: {asset} @ ${price:.4f} | "
            f"Units: {units:.4f} | Cost: ${total_cost:.2f}"
        )

    def _close_position(self, asset: str, price: float, exit_date: date,
                       exit_reason: str):
        """Close an existing position."""
        if asset not in self.positions:
            return

        position = self.positions[asset]

        # Calculate exit value
        exit_value = position.units * price
        exit_fee = exit_value * (self.exit_fee_pct / 100.0)
        net_proceeds = exit_value - exit_fee

        # Add cash back
        self.cash += Decimal(str(net_proceeds))

        # Update position
        position.exit_date = exit_date
        position.exit_price = price
        position.exit_value = net_proceeds
        position.exit_reason = exit_reason
        position.pnl = net_proceeds - position.cost_basis
        position.pnl_pct = (position.pnl / position.cost_basis) * 100

        # Move to closed trades
        self.closed_trades.append(position)
        del self.positions[asset]

        logger.debug(
            f"EXIT: {asset} @ ${price:.4f} | "
            f"PnL: ${position.pnl:.2f} ({position.pnl_pct:+.2f}%) | "
            f"Reason: {exit_reason}"
        )

    def _close_all_positions(self, end_date: date,
                            historical_data: Dict[str, List[Dict]]):
        """Close all remaining positions at end of backtest."""
        logger.info(f"Closing {len(self.positions)} remaining positions...")

        for asset in list(self.positions.keys()):
            # Get last available price
            candles = historical_data.get(asset, [])
            last_candle = None
            for candle in reversed(candles):
                if candle['date'] <= end_date:
                    last_candle = candle
                    break

            if last_candle:
                self._close_position(
                    asset,
                    last_candle['close'],
                    end_date,
                    "End of backtest"
                )

    def _calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        positions_value = sum(
            pos.units * current_prices.get(pos.asset, pos.entry_price)
            for pos in self.positions.values()
        )
        return float(self.cash) + positions_value

    def _calculate_performance_metrics(self, start_date: date,
                                       end_date: date) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        if not self.equity_curve:
            return {}

        initial_value = self.equity_curve[0]['total_value']
        final_value = self.equity_curve[-1]['total_value']

        # Total return
        total_return = ((final_value - initial_value) / initial_value) * 100

        # Winning and losing trades
        winners = [t for t in self.closed_trades if t.pnl > 0]
        losers = [t for t in self.closed_trades if t.pnl <= 0]

        win_rate = (len(winners) / len(self.closed_trades) * 100) if self.closed_trades else 0

        avg_win = np.mean([t.pnl_pct for t in winners]) if winners else 0
        avg_loss = np.mean([t.pnl_pct for t in losers]) if losers else 0

        # Max drawdown
        max_dd = self._calculate_max_drawdown()

        # Sharpe ratio (assuming 252 trading days per year)
        if len(self.daily_returns) > 1:
            returns_std = np.std(self.daily_returns)
            avg_daily_return = np.mean(self.daily_returns)
            sharpe = (avg_daily_return / returns_std) * np.sqrt(252) if returns_std > 0 else 0
        else:
            sharpe = 0

        # Trade breakdown by exit reason
        exit_reasons = defaultdict(int)
        for trade in self.closed_trades:
            exit_reasons[trade.exit_reason] += 1

        # Days in backtest
        days = (end_date - start_date).days

        results = {
            'start_date': start_date,
            'end_date': end_date,
            'days': days,
            'initial_balance': initial_value,
            'final_balance': final_value,
            'total_return': total_return,
            'total_pnl': final_value - initial_value,
            'total_trades': len(self.closed_trades),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': win_rate,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'best_trade_pct': max([t.pnl_pct for t in self.closed_trades]) if self.closed_trades else 0,
            'worst_trade_pct': min([t.pnl_pct for t in self.closed_trades]) if self.closed_trades else 0,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'exit_reasons': dict(exit_reasons),
            'equity_curve': self.equity_curve,
            'closed_trades': self.closed_trades
        }

        return results

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage."""
        if not self.equity_curve:
            return 0

        values = [point['total_value'] for point in self.equity_curve]
        max_dd = 0
        peak = values[0]

        for value in values:
            if value > peak:
                peak = value
            dd = ((peak - value) / peak) * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def print_results(self, results: Dict[str, Any]):
        """Print formatted backtest results."""
        print("\n" + "=" * 80)
        print("📊 BACKTEST RESULTS")
        print("=" * 80)
        print(f"\nPeriod: {results['start_date']} to {results['end_date']} ({results['days']} days)")
        print(f"\nInitial Balance: ${results['initial_balance']:,.2f}")
        print(f"Final Balance:   ${results['final_balance']:,.2f}")
        print(f"Total Return:    {results['total_return']:+.2f}%")
        print(f"Total PnL:       ${results['total_pnl']:+,.2f}")

        print(f"\n{'─' * 80}")
        print("TRADE STATISTICS")
        print(f"{'─' * 80}")
        print(f"Total Trades:    {results['total_trades']}")
        print(f"Winners:         {results['winners']} ({results['win_rate']:.1f}%)")
        print(f"Losers:          {results['losers']}")
        print(f"Avg Win:         {results['avg_win_pct']:+.2f}%")
        print(f"Avg Loss:        {results['avg_loss_pct']:+.2f}%")
        print(f"Best Trade:      {results['best_trade_pct']:+.2f}%")
        print(f"Worst Trade:     {results['worst_trade_pct']:+.2f}%")

        print(f"\n{'─' * 80}")
        print("RISK METRICS")
        print(f"{'─' * 80}")
        print(f"Max Drawdown:    {results['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio:    {results['sharpe_ratio']:.2f}")

        print(f"\n{'─' * 80}")
        print("EXIT REASONS")
        print(f"{'─' * 80}")
        for reason, count in results['exit_reasons'].items():
            pct = (count / results['total_trades']) * 100
            print(f"{reason:30s} {count:4d} ({pct:.1f}%)")

        print("\n" + "=" * 80)
