"""
Position manager for tracking and managing open positions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages open positions, including tracking highest values for trailing stops."""

    def __init__(self, storage):
        """
        Initialize position manager.

        Args:
            storage: DatabaseStorage instance
        """
        self.storage = storage
        self.positions_cache = {}  # In-memory cache of open positions

    def refresh_positions(self):
        """Refresh positions from database."""
        open_positions = self.storage.get_open_positions()
        self.positions_cache = {pos['asset']: pos for pos in open_positions}
        logger.debug(f"Refreshed {len(self.positions_cache)} open positions")

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return list(self.positions_cache.values())

    def get_position(self, asset: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific asset."""
        return self.positions_cache.get(asset)

    def has_position(self, asset: str) -> bool:
        """Check if position exists for an asset."""
        return asset in self.positions_cache

    def get_open_position_symbols(self) -> List[str]:
        """Get list of assets with open positions."""
        return list(self.positions_cache.keys())

    def add_position(self, asset: str, entry_trade_id: str, units: float,
                    entry_price: float, entry_time: datetime):
        """
        Add a new position.

        Args:
            asset: Asset symbol
            entry_trade_id: Trade ID of the entry trade
            units: Number of units
            entry_price: Entry price per unit
            entry_time: Entry timestamp
        """
        position = {
            'asset': asset,
            'entry_trade_id': entry_trade_id,
            'units': units,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'current_price': entry_price,
            'current_value': units * entry_price,
            'highest_value': units * entry_price,
            'unrealized_pnl': 0,
            'unrealized_pnl_percentage': 0,
            'status': 'OPEN'
        }

        # Insert into database
        self.storage.insert_position(position)

        # Add to cache
        self.positions_cache[asset] = position

        logger.info(f"Added position: {asset} @ {entry_price} x {units} units")

    def update_position_prices(self, current_prices: Dict[str, float]):
        """
        Update current prices and values for all positions.

        Args:
            current_prices: Dictionary mapping assets to current prices
        """
        for asset, position in self.positions_cache.items():
            if asset not in current_prices:
                logger.warning(f"No current price for {asset}")
                continue

            current_price = current_prices[asset]
            units = float(position['units'])
            entry_price = float(position['entry_price'])

            # Calculate current value
            current_value = units * current_price

            # Update highest value if needed
            highest_value = float(position['highest_value'])
            if current_value > highest_value:
                highest_value = current_value

            # Calculate unrealized P&L
            cost_basis = units * entry_price
            unrealized_pnl = current_value - cost_basis
            unrealized_pnl_pct = (unrealized_pnl / cost_basis) * 100

            # Update database
            updates = {
                'current_price': current_price,
                'current_value': current_value,
                'highest_value': highest_value,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_percentage': unrealized_pnl_pct
            }

            self.storage.update_position(asset, updates)

            # Update cache
            position.update(updates)

            logger.debug(f"Updated {asset}: price={current_price:.4f}, value={current_value:.2f}, "
                        f"highest={highest_value:.2f}, pnl={unrealized_pnl_pct:.2f}%")

    def close_position(self, asset: str):
        """
        Close a position.

        Args:
            asset: Asset symbol
        """
        if asset not in self.positions_cache:
            logger.warning(f"Cannot close position for {asset}: not found")
            return

        # Update database
        self.storage.close_position(asset)

        # Remove from cache
        del self.positions_cache[asset]

        logger.info(f"Closed position: {asset}")

    def get_total_positions_value(self) -> float:
        """Calculate total value of all open positions."""
        total = sum(float(pos['current_value']) for pos in self.positions_cache.values())
        return total

    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.positions_cache)

    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions."""
        if not self.positions_cache:
            return {
                'count': 0,
                'total_value': 0,
                'total_unrealized_pnl': 0,
                'positions': []
            }

        total_value = 0
        total_unrealized_pnl = 0
        positions_summary = []

        for asset, pos in self.positions_cache.items():
            total_value += float(pos['current_value'])
            total_unrealized_pnl += float(pos['unrealized_pnl'])

            positions_summary.append({
                'asset': asset,
                'units': float(pos['units']),
                'entry_price': float(pos['entry_price']),
                'current_price': float(pos['current_price']),
                'current_value': float(pos['current_value']),
                'unrealized_pnl': float(pos['unrealized_pnl']),
                'unrealized_pnl_pct': float(pos['unrealized_pnl_percentage']),
                'entry_time': pos['entry_time']
            })

        return {
            'count': len(self.positions_cache),
            'total_value': total_value,
            'total_unrealized_pnl': total_unrealized_pnl,
            'positions': positions_summary
        }
