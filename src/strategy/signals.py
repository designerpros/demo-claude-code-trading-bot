"""
Signal generation module for entry and exit trading signals.
"""

from typing import List, Dict, Any, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates entry and exit signals based on technical indicators and rules."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize signal generator.

        Args:
            config: Configuration dictionary with indicator and exit parameters
        """
        self.config = config
        self.indicators_config = config.get('indicators', {})
        self.exits_config = config.get('exits', {})

        # Entry parameters
        self.ema_fast = self.indicators_config.get('ema_fast', 12)
        self.ema_slow = self.indicators_config.get('ema_slow', 48)
        self.rsi_period = self.indicators_config.get('rsi_period', 14)
        self.rsi_oversold = self.indicators_config.get('rsi_oversold', 30)
        self.atr_period = self.indicators_config.get('atr_period', 10)
        self.atr_multiplier = self.indicators_config.get('atr_multiplier', 0.1)
        self.crossover_lookback = self.indicators_config.get('crossover_lookback', 5)

        # Exit parameters
        self.stop_loss_pct = self.exits_config.get('stop_loss_percentage', 25.0)
        self.trailing_stop_pct = self.exits_config.get('trailing_stop_percentage', 30.0)

    # ==================== Entry Signals ====================

    def generate_entry_signals(self, indicators_by_asset: Dict[str, List[Dict[str, Any]]],
                              open_positions: List[str]) -> List[str]:
        """
        Generate entry signals for all tracked assets.

        Entry conditions (ALL must be met):
        1. No position exists in that asset
        2. Fast EMA (12) crossed above Slow EMA (48) within last 5 candles
        3. ONE of:
           a. RSI < 30 (oversold)
           b. abs(close_today - close_yesterday) > 0.1 * ATR(10)

        Args:
            indicators_by_asset: Dictionary mapping asset symbols to their indicator history
            open_positions: List of asset symbols with open positions

        Returns:
            List of asset symbols with entry signals
        """
        entry_signals = []

        for asset, indicators in indicators_by_asset.items():
            # Condition 1: No existing position
            if asset in open_positions:
                logger.debug(f"{asset}: Already has open position, skipping")
                continue

            # Need at least lookback + 1 candles
            if len(indicators) < self.crossover_lookback + 1:
                logger.debug(f"{asset}: Insufficient indicator history")
                continue

            # Get latest indicators
            latest = indicators[-1]

            # Condition 2: EMA crossover within last N candles
            if not self._check_ema_crossover_in_window(indicators, self.crossover_lookback):
                logger.debug(f"{asset}: No EMA crossover in last {self.crossover_lookback} candles")
                continue

            # Condition 3: RSI oversold OR ATR breakout
            rsi_oversold = latest.get('rsi_14', 100) < self.rsi_oversold
            atr_breakout = latest.get('atr_breakout', False)

            if not (rsi_oversold or atr_breakout):
                logger.debug(f"{asset}: Neither RSI oversold nor ATR breakout condition met")
                continue

            # All conditions met!
            entry_signals.append(asset)
            logger.info(f"{asset}: ENTRY SIGNAL - EMA crossover: Yes, RSI oversold: {rsi_oversold}, ATR breakout: {atr_breakout}")

        return entry_signals

    def _check_ema_crossover_in_window(self, indicators: List[Dict[str, Any]],
                                      window: int) -> bool:
        """
        Check if fast EMA crossed above slow EMA within the last N candles.

        Args:
            indicators: List of indicator dictionaries (sorted by date)
            window: Number of candles to look back

        Returns:
            True if crossover detected
        """
        if len(indicators) < 2:
            return False

        # Look at the last 'window' indicators
        recent_indicators = indicators[-window - 1:] if len(indicators) > window else indicators

        # Check for bullish crossover in this window
        for i in range(1, len(recent_indicators)):
            prev = recent_indicators[i - 1]
            curr = recent_indicators[i]

            prev_ema_12 = prev.get('ema_12')
            prev_ema_48 = prev.get('ema_48')
            curr_ema_12 = curr.get('ema_12')
            curr_ema_48 = curr.get('ema_48')

            if all([prev_ema_12, prev_ema_48, curr_ema_12, curr_ema_48]):
                # Bullish crossover: fast was below slow, now fast is above slow
                if prev_ema_12 < prev_ema_48 and curr_ema_12 > curr_ema_48:
                    return True

        return False

    # ==================== Exit Signals ====================

    def generate_exit_signals(self, positions: List[Dict[str, Any]],
                            current_prices: Dict[str, float],
                            indicators_by_asset: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
        """
        Generate exit signals for open positions.

        Exit conditions (ANY triggers exit):
        1. 25% stop loss from entry
        2. 30% trailing stop from highest value
        3. Slow EMA (48) crosses above Fast EMA (12) from below (bearish reversal)

        Args:
            positions: List of open position dictionaries
            current_prices: Dictionary mapping assets to current prices
            indicators_by_asset: Dictionary mapping asset symbols to their indicator history

        Returns:
            Dictionary mapping assets to exit reasons
        """
        exit_signals = {}

        for position in positions:
            asset = position['asset']
            entry_price = float(position['entry_price'])
            highest_value = float(position.get('highest_value', position['current_value']))
            current_price = current_prices.get(asset)

            if not current_price:
                logger.warning(f"{asset}: No current price available, skipping exit check")
                continue

            current_value = float(position['units']) * current_price

            # Exit condition 1: Stop loss (25% from entry)
            loss_from_entry = (entry_price - current_price) / entry_price * 100
            if loss_from_entry >= self.stop_loss_pct:
                exit_signals[asset] = f"Stop loss triggered: {loss_from_entry:.2f}% loss from entry"
                logger.info(f"{asset}: EXIT SIGNAL - {exit_signals[asset]}")
                continue

            # Exit condition 2: Trailing stop (30% from highest value)
            if highest_value > 0:
                loss_from_peak = (highest_value - current_value) / highest_value * 100
                if loss_from_peak >= self.trailing_stop_pct:
                    exit_signals[asset] = f"Trailing stop triggered: {loss_from_peak:.2f}% loss from peak"
                    logger.info(f"{asset}: EXIT SIGNAL - {exit_signals[asset]}")
                    continue

            # Exit condition 3: Bearish EMA crossover (slow crosses above fast)
            if asset in indicators_by_asset:
                indicators = indicators_by_asset[asset]
                if self._check_bearish_crossover(indicators):
                    exit_signals[asset] = "Bearish EMA crossover: Slow EMA crossed above Fast EMA"
                    logger.info(f"{asset}: EXIT SIGNAL - {exit_signals[asset]}")
                    continue

        return exit_signals

    def _check_bearish_crossover(self, indicators: List[Dict[str, Any]]) -> bool:
        """
        Check if slow EMA crossed above fast EMA (bearish signal).

        Args:
            indicators: List of indicator dictionaries (sorted by date)

        Returns:
            True if bearish crossover detected in latest candle
        """
        if len(indicators) < 2:
            return False

        # Check the latest two candles
        prev = indicators[-2]
        curr = indicators[-1]

        prev_ema_12 = prev.get('ema_12')
        prev_ema_48 = prev.get('ema_48')
        curr_ema_12 = curr.get('ema_12')
        curr_ema_48 = curr.get('ema_48')

        if not all([prev_ema_12, prev_ema_48, curr_ema_12, curr_ema_48]):
            return False

        # Bearish crossover: fast was above slow, now fast is below slow
        return prev_ema_12 > prev_ema_48 and curr_ema_12 < curr_ema_48

    # ==================== Signal Evaluation ====================

    def evaluate_entry_signal(self, asset: str, indicators: List[Dict[str, Any]],
                             has_position: bool) -> Dict[str, Any]:
        """
        Evaluate entry signal for a single asset with detailed breakdown.

        Args:
            asset: Asset symbol
            indicators: List of indicator dictionaries for the asset
            has_position: Whether position already exists

        Returns:
            Dictionary with signal evaluation details
        """
        evaluation = {
            'asset': asset,
            'signal': False,
            'conditions': {
                'no_position': not has_position,
                'ema_crossover': False,
                'rsi_oversold': False,
                'atr_breakout': False
            },
            'details': {}
        }

        if has_position:
            evaluation['details']['reason'] = "Already has open position"
            return evaluation

        if len(indicators) < self.crossover_lookback + 1:
            evaluation['details']['reason'] = "Insufficient indicator history"
            return evaluation

        latest = indicators[-1]

        # Check EMA crossover
        evaluation['conditions']['ema_crossover'] = self._check_ema_crossover_in_window(
            indicators, self.crossover_lookback
        )

        # Check RSI oversold
        rsi = latest.get('rsi_14')
        if rsi is not None:
            evaluation['conditions']['rsi_oversold'] = rsi < self.rsi_oversold
            evaluation['details']['rsi'] = rsi

        # Check ATR breakout
        evaluation['conditions']['atr_breakout'] = latest.get('atr_breakout', False)
        if latest.get('atr_10'):
            evaluation['details']['atr'] = latest['atr_10']
        if latest.get('price_change'):
            evaluation['details']['price_change'] = latest['price_change']

        # Determine overall signal
        ema_ok = evaluation['conditions']['ema_crossover']
        momentum_ok = evaluation['conditions']['rsi_oversold'] or evaluation['conditions']['atr_breakout']

        evaluation['signal'] = ema_ok and momentum_ok

        return evaluation

    def evaluate_exit_signal(self, asset: str, position: Dict[str, Any],
                           current_price: float,
                           indicators: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate exit signal for a position with detailed breakdown.

        Args:
            asset: Asset symbol
            position: Position dictionary
            current_price: Current asset price
            indicators: List of indicator dictionaries for the asset

        Returns:
            Dictionary with exit evaluation details
        """
        evaluation = {
            'asset': asset,
            'signal': False,
            'reason': None,
            'conditions': {
                'stop_loss': False,
                'trailing_stop': False,
                'bearish_crossover': False
            },
            'details': {}
        }

        entry_price = float(position['entry_price'])
        highest_value = float(position.get('highest_value', position['current_value']))
        current_value = float(position['units']) * current_price

        # Check stop loss
        loss_from_entry = (entry_price - current_price) / entry_price * 100
        evaluation['details']['loss_from_entry'] = loss_from_entry
        evaluation['conditions']['stop_loss'] = loss_from_entry >= self.stop_loss_pct

        # Check trailing stop
        if highest_value > 0:
            loss_from_peak = (highest_value - current_value) / highest_value * 100
            evaluation['details']['loss_from_peak'] = loss_from_peak
            evaluation['conditions']['trailing_stop'] = loss_from_peak >= self.trailing_stop_pct

        # Check bearish crossover
        evaluation['conditions']['bearish_crossover'] = self._check_bearish_crossover(indicators)

        # Determine overall signal and reason
        if evaluation['conditions']['stop_loss']:
            evaluation['signal'] = True
            evaluation['reason'] = f"Stop loss triggered: {loss_from_entry:.2f}% loss"
        elif evaluation['conditions']['trailing_stop']:
            evaluation['signal'] = True
            evaluation['reason'] = f"Trailing stop triggered: {loss_from_peak:.2f}% from peak"
        elif evaluation['conditions']['bearish_crossover']:
            evaluation['signal'] = True
            evaluation['reason'] = "Bearish EMA crossover"

        return evaluation
