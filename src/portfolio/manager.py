"""
Portfolio manager for tracking cash, positions, and overall portfolio value.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio state including cash and positions."""

    def __init__(self, storage, initial_balance: float = 10000.0):
        """
        Initialize portfolio manager.

        Args:
            storage: DatabaseStorage instance
            initial_balance: Initial cash balance in USDT
        """
        self.storage = storage
        self.initial_balance = Decimal(str(initial_balance))
        self.cash = Decimal(str(initial_balance))  # Available liquidity
        self.previous_total_value = None

    def get_cash(self) -> float:
        """Get available cash (liquidity)."""
        return float(self.cash)

    def get_total_value(self, positions_value: float) -> float:
        """
        Calculate total portfolio value.

        Args:
            positions_value: Total value of open positions

        Returns:
            Total portfolio value (cash + positions)
        """
        return float(self.cash) + positions_value

    def add_cash(self, amount: float):
        """
        Add cash to portfolio (from closing positions).

        Args:
            amount: Amount to add
        """
        self.cash += Decimal(str(amount))
        logger.debug(f"Added ${amount:.2f} cash, new balance: ${float(self.cash):.2f}")

    def remove_cash(self, amount: float) -> bool:
        """
        Remove cash from portfolio (for opening positions).

        Args:
            amount: Amount to remove

        Returns:
            True if successful, False if insufficient cash
        """
        amount_decimal = Decimal(str(amount))

        if amount_decimal > self.cash:
            logger.warning(f"Insufficient cash: need ${amount:.2f}, have ${float(self.cash):.2f}")
            return False

        self.cash -= amount_decimal
        logger.debug(f"Removed ${amount:.2f} cash, new balance: ${float(self.cash):.2f}")
        return True

    def calculate_position_size(self, price: float, size_percentage: float = 5.0) -> tuple[float, float]:
        """
        Calculate position size based on available liquidity.

        Args:
            price: Asset price
            size_percentage: Percentage of available liquidity to use (default 5%)

        Returns:
            Tuple of (units, value) for the position
        """
        # Position size is percentage of available liquidity
        position_value = float(self.cash) * (size_percentage / 100.0)

        # Calculate number of units
        units = position_value / price

        logger.debug(f"Position size: ${position_value:.2f} ({size_percentage}% of ${float(self.cash):.2f}) = {units:.6f} units @ ${price:.4f}")

        return units, position_value

    def can_open_position(self, value: float) -> bool:
        """
        Check if there's enough cash to open a position.

        Args:
            value: Position value including fees

        Returns:
            True if sufficient cash available
        """
        return Decimal(str(value)) <= self.cash

    def take_snapshot(self, timestamp: datetime, positions_value: float,
                     num_positions: int) -> Dict[str, Any]:
        """
        Create a portfolio snapshot.

        Args:
            timestamp: Snapshot timestamp
            positions_value: Total value of open positions
            num_positions: Number of open positions

        Returns:
            Portfolio snapshot dictionary
        """
        cash = float(self.cash)
        total_value = cash + positions_value

        # Calculate percentages
        cash_pct = (cash / total_value * 100) if total_value > 0 else 100
        positions_pct = (positions_value / total_value * 100) if total_value > 0 else 0

        # Calculate daily P&L if we have previous value
        daily_pnl = None
        daily_pnl_pct = None

        if self.previous_total_value is not None:
            daily_pnl = total_value - self.previous_total_value
            if self.previous_total_value > 0:
                daily_pnl_pct = (daily_pnl / self.previous_total_value) * 100

        snapshot = {
            'timestamp': timestamp,
            'total_value': total_value,
            'cash': cash,
            'positions_value': positions_value,
            'cash_percentage': cash_pct,
            'positions_percentage': positions_pct,
            'num_positions': num_positions,
            'daily_pnl': daily_pnl,
            'daily_pnl_percentage': daily_pnl_pct
        }

        # Save to database
        self.storage.insert_portfolio_snapshot(snapshot)

        # Update previous value for next calculation
        self.previous_total_value = total_value

        logger.info(f"Portfolio snapshot: Total=${total_value:.2f}, Cash={cash_pct:.1f}%, "
                   f"Positions={positions_pct:.1f}%, Count={num_positions}")

        if daily_pnl is not None:
            logger.info(f"Daily P&L: ${daily_pnl:.2f} ({daily_pnl_pct:.2f}%)")

        return snapshot

    def get_portfolio_summary(self, positions_value: float,
                             num_positions: int) -> Dict[str, Any]:
        """
        Get current portfolio summary without saving snapshot.

        Args:
            positions_value: Total value of open positions
            num_positions: Number of open positions

        Returns:
            Portfolio summary dictionary
        """
        cash = float(self.cash)
        total_value = cash + positions_value

        cash_pct = (cash / total_value * 100) if total_value > 0 else 100
        positions_pct = (positions_value / total_value * 100) if total_value > 0 else 0

        # Calculate total return
        total_return = total_value - float(self.initial_balance)
        total_return_pct = (total_return / float(self.initial_balance)) * 100

        return {
            'total_value': total_value,
            'cash': cash,
            'positions_value': positions_value,
            'cash_percentage': cash_pct,
            'positions_percentage': positions_pct,
            'num_positions': num_positions,
            'initial_balance': float(self.initial_balance),
            'total_return': total_return,
            'total_return_percentage': total_return_pct
        }

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get the most recent portfolio snapshot from database."""
        return self.storage.get_latest_portfolio_snapshot()

    def get_portfolio_history(self, days: int = 30) -> list:
        """
        Get portfolio history for the last N days.

        Args:
            days: Number of days of history

        Returns:
            List of portfolio snapshots
        """
        return self.storage.get_portfolio_history(days)

    def initialize_from_snapshot(self):
        """Initialize portfolio state from latest snapshot if available."""
        latest_snapshot = self.get_latest_snapshot()

        if latest_snapshot:
            self.cash = Decimal(str(latest_snapshot['cash']))
            self.previous_total_value = float(latest_snapshot['total_value'])
            logger.info(f"Initialized portfolio from snapshot: Cash=${float(self.cash):.2f}, "
                       f"Total=${self.previous_total_value:.2f}")
        else:
            logger.info(f"Starting new portfolio with ${float(self.initial_balance):.2f}")
