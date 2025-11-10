"""
Paper trading engine for simulating trades without real money.
"""

import uuid
from typing import Dict, Any, List, Tuple
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PaperTrader:
    """Simulates trading with paper money."""

    def __init__(self, storage, portfolio_manager, position_manager, config: Dict[str, Any]):
        """
        Initialize paper trader.

        Args:
            storage: DatabaseStorage instance
            portfolio_manager: PortfolioManager instance
            position_manager: PositionManager instance
            config: Trading configuration
        """
        self.storage = storage
        self.portfolio = portfolio_manager
        self.positions = position_manager
        self.config = config

        # Fee structure
        self.entry_fee_pct = config.get('entry_fee_percentage', 0.5)
        self.exit_fee_pct = config.get('exit_fee_percentage', 1.0)

        # Position sizing
        self.position_size_pct = config.get('position_size_percentage', 5.0)

    def execute_entries(self, entry_signals: List[str], current_prices: Dict[str, float],
                       timestamp: datetime) -> List[str]:
        """
        Execute entry trades for assets with signals.

        Args:
            entry_signals: List of asset symbols with entry signals
            current_prices: Dictionary mapping assets to current prices
            timestamp: Trade timestamp

        Returns:
            List of trade IDs for executed entries
        """
        executed_trades = []

        for asset in entry_signals:
            if asset not in current_prices:
                logger.warning(f"{asset}: No price available, skipping entry")
                continue

            try:
                trade_id = self._execute_entry(asset, current_prices[asset], timestamp)
                if trade_id:
                    executed_trades.append(trade_id)
            except Exception as e:
                logger.error(f"Error executing entry for {asset}: {e}")
                continue

        return executed_trades

    def _execute_entry(self, asset: str, price: float, timestamp: datetime) -> str:
        """
        Execute a single entry trade.

        Args:
            asset: Asset symbol
            price: Entry price
            timestamp: Trade timestamp

        Returns:
            Trade ID if successful, None otherwise
        """
        # Calculate position size
        units, position_value = self.portfolio.calculate_position_size(price, self.position_size_pct)

        if units <= 0:
            logger.warning(f"{asset}: Position size is 0, skipping")
            return None

        # Calculate entry fee
        entry_fee = position_value * (self.entry_fee_pct / 100.0)
        total_cost = position_value + entry_fee

        # Check if we have enough cash
        if not self.portfolio.can_open_position(total_cost):
            logger.warning(f"{asset}: Insufficient cash for entry (need ${total_cost:.2f}, "
                         f"have ${self.portfolio.get_cash():.2f})")
            return None

        # Record liquidity before trade
        liquidity_before = self.portfolio.get_cash()

        # Execute trade: remove cash from portfolio
        if not self.portfolio.remove_cash(total_cost):
            return None

        liquidity_after = self.portfolio.get_cash()

        # Generate trade ID
        trade_id = f"ENTRY_{asset}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Create trade record
        trade = {
            'trade_id': trade_id,
            'asset': asset,
            'trade_type': 'ENTRY',
            'timestamp': timestamp,
            'price': price,
            'units': units,
            'value': position_value,
            'fee': entry_fee,
            'fee_percentage': self.entry_fee_pct / 100.0,
            'liquidity_before': liquidity_before,
            'liquidity_after': liquidity_after,
            'entry_trade_id': trade_id,  # Self-reference for entry trades
            'exit_trade_id': None
        }

        # Save trade to database
        self.storage.insert_trade(trade)

        # Add position
        self.positions.add_position(asset, trade_id, units, price, timestamp)

        logger.info(f"✅ ENTRY: {asset} | Price: ${price:.4f} | Units: {units:.6f} | "
                   f"Value: ${position_value:.2f} | Fee: ${entry_fee:.2f} | "
                   f"Cash: ${liquidity_after:.2f}")

        return trade_id

    def execute_exits(self, exit_signals: Dict[str, str], current_prices: Dict[str, float],
                     timestamp: datetime) -> List[Tuple[str, str]]:
        """
        Execute exit trades for positions with signals.

        Args:
            exit_signals: Dictionary mapping assets to exit reasons
            current_prices: Dictionary mapping assets to current prices
            timestamp: Trade timestamp

        Returns:
            List of tuples (entry_trade_id, exit_trade_id)
        """
        executed_trades = []

        for asset, reason in exit_signals.items():
            if asset not in current_prices:
                logger.warning(f"{asset}: No price available, skipping exit")
                continue

            try:
                entry_id, exit_id = self._execute_exit(asset, current_prices[asset], timestamp, reason)
                if entry_id and exit_id:
                    executed_trades.append((entry_id, exit_id))
            except Exception as e:
                logger.error(f"Error executing exit for {asset}: {e}")
                continue

        return executed_trades

    def _execute_exit(self, asset: str, price: float, timestamp: datetime,
                     reason: str) -> Tuple[str, str]:
        """
        Execute a single exit trade.

        Args:
            asset: Asset symbol
            price: Exit price
            timestamp: Trade timestamp
            reason: Exit reason

        Returns:
            Tuple of (entry_trade_id, exit_trade_id) if successful
        """
        # Get position
        position = self.positions.get_position(asset)

        if not position:
            logger.warning(f"{asset}: No position found, cannot exit")
            return None, None

        entry_trade_id = position['entry_trade_id']
        units = float(position['units'])
        entry_price = float(position['entry_price'])
        entry_time = position['entry_time']

        # Calculate exit value
        exit_value = units * price

        # Calculate exit fee
        exit_fee = exit_value * (self.exit_fee_pct / 100.0)

        # Net proceeds after fee
        net_proceeds = exit_value - exit_fee

        # Record liquidity before trade
        liquidity_before = self.portfolio.get_cash()

        # Execute trade: add cash to portfolio
        self.portfolio.add_cash(net_proceeds)

        liquidity_after = self.portfolio.get_cash()

        # Calculate P&L
        cost_basis = units * entry_price + (units * entry_price * self.entry_fee_pct / 100.0)
        profit_loss = net_proceeds - cost_basis
        profit_loss_pct = (profit_loss / cost_basis) * 100

        # Calculate time in trade
        time_in_trade = timestamp - entry_time
        time_in_trade_hours = time_in_trade.total_seconds() / 3600

        # Generate trade ID
        exit_trade_id = f"EXIT_{asset}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Create trade record
        trade = {
            'trade_id': exit_trade_id,
            'asset': asset,
            'trade_type': 'EXIT',
            'timestamp': timestamp,
            'price': price,
            'units': units,
            'value': exit_value,
            'fee': exit_fee,
            'fee_percentage': self.exit_fee_pct / 100.0,
            'liquidity_before': liquidity_before,
            'liquidity_after': liquidity_after,
            'entry_trade_id': entry_trade_id,
            'exit_trade_id': exit_trade_id,
            'time_in_trade_hours': time_in_trade_hours,
            'profit_loss': profit_loss,
            'profit_loss_percentage': profit_loss_pct,
            'exit_reason': reason
        }

        # Save trade to database
        self.storage.insert_trade(trade)

        # Update entry trade with exit mapping
        self.storage.update_trade_exit_mapping(entry_trade_id, exit_trade_id)

        # Close position
        self.positions.close_position(asset)

        logger.info(f"❌ EXIT: {asset} | Price: ${price:.4f} | Units: {units:.6f} | "
                   f"Value: ${exit_value:.2f} | Fee: ${exit_fee:.2f} | "
                   f"P&L: ${profit_loss:.2f} ({profit_loss_pct:.2f}%) | "
                   f"Time: {time_in_trade_hours:.1f}h | Reason: {reason} | "
                   f"Cash: ${liquidity_after:.2f}")

        return entry_trade_id, exit_trade_id

    def get_trading_summary(self) -> Dict[str, Any]:
        """Get summary of all trades."""
        all_trades = self.storage.get_all_trades()

        if not all_trades:
            return {
                'total_trades': 0,
                'entries': 0,
                'exits': 0,
                'total_fees': 0,
                'total_pnl': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0
            }

        entries = [t for t in all_trades if t['trade_type'] == 'ENTRY']
        exits = [t for t in all_trades if t['trade_type'] == 'EXIT']

        total_fees = sum(float(t['fee']) for t in all_trades)
        total_pnl = sum(float(t.get('profit_loss', 0)) for t in exits if t.get('profit_loss'))

        winning_trades = sum(1 for t in exits if t.get('profit_loss') and float(t['profit_loss']) > 0)
        losing_trades = sum(1 for t in exits if t.get('profit_loss') and float(t['profit_loss']) <= 0)

        win_rate = (winning_trades / len(exits) * 100) if exits else 0

        return {
            'total_trades': len(all_trades),
            'entries': len(entries),
            'exits': len(exits),
            'total_fees': total_fees,
            'total_pnl': total_pnl,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate
        }
