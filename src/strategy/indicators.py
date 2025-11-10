"""
Technical indicators module for calculating EMA, RSI, and ATR.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculates technical indicators for trading signals."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize technical indicators calculator.

        Args:
            config: Indicator configuration dictionary
        """
        self.ema_fast = config.get('ema_fast', 12)
        self.ema_slow = config.get('ema_slow', 48)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.atr_period = config.get('atr_period', 10)
        self.atr_multiplier = config.get('atr_multiplier', 0.1)
        self.crossover_lookback = config.get('crossover_lookback', 5)

    def calculate_all_indicators(self, daily_candles: List[Dict[str, Any]],
                                 asset: str) -> List[Dict[str, Any]]:
        """
        Calculate all indicators for an asset.

        Args:
            daily_candles: List of daily candle dictionaries
            asset: Asset symbol

        Returns:
            List of indicator dictionaries with date, asset, and all indicator values
        """
        if not daily_candles or len(daily_candles) < max(self.ema_slow, self.rsi_period, self.atr_period):
            logger.warning(f"Insufficient data for {asset}: need at least {max(self.ema_slow, self.rsi_period, self.atr_period)} candles")
            return []

        # Convert to DataFrame
        df = pd.DataFrame(daily_candles)

        # Ensure date column is date type
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.date

        # Sort by date
        df.sort_values('date', inplace=True)

        # Calculate EMAs
        df['ema_12'] = ta.ema(df['close'], length=self.ema_fast)
        df['ema_48'] = ta.ema(df['close'], length=self.ema_slow)

        # Calculate RSI
        df['rsi_14'] = ta.rsi(df['close'], length=self.rsi_period)

        # Calculate ATR
        df['atr_10'] = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)

        # Calculate price change
        df['price_change'] = df['close'].diff()

        # Detect EMA crossover within last N candles
        df['ema_crossover_signal'] = self._detect_ema_crossover(
            df['ema_12'].values,
            df['ema_48'].values,
            self.crossover_lookback
        )

        # Detect RSI oversold
        df['rsi_oversold'] = df['rsi_14'] < self.rsi_oversold

        # Detect ATR breakout
        df['atr_breakout'] = abs(df['price_change']) > (self.atr_multiplier * df['atr_10'])

        # Convert to list of dictionaries
        indicators = []
        for _, row in df.iterrows():
            if pd.notna(row['ema_12']) and pd.notna(row['ema_48']):
                indicators.append({
                    'date': row['date'],
                    'asset': asset,
                    'ema_12': float(row['ema_12']) if pd.notna(row['ema_12']) else None,
                    'ema_48': float(row['ema_48']) if pd.notna(row['ema_48']) else None,
                    'rsi_14': float(row['rsi_14']) if pd.notna(row['rsi_14']) else None,
                    'atr_10': float(row['atr_10']) if pd.notna(row['atr_10']) else None,
                    'price_change': float(row['price_change']) if pd.notna(row['price_change']) else None,
                    'ema_crossover_signal': bool(row['ema_crossover_signal']),
                    'rsi_oversold': bool(row['rsi_oversold']) if pd.notna(row['rsi_oversold']) else False,
                    'atr_breakout': bool(row['atr_breakout']) if pd.notna(row['atr_breakout']) else False
                })

        logger.debug(f"Calculated indicators for {asset}: {len(indicators)} records")

        return indicators

    def _detect_ema_crossover(self, ema_fast: np.ndarray, ema_slow: np.ndarray,
                             lookback: int) -> np.ndarray:
        """
        Detect if fast EMA crossed above slow EMA within the last N periods.

        Args:
            ema_fast: Fast EMA values
            ema_slow: Slow EMA values
            lookback: Number of periods to look back

        Returns:
            Boolean array indicating crossover signals
        """
        signals = np.zeros(len(ema_fast), dtype=bool)

        # Calculate the difference (positive when fast > slow)
        diff = ema_fast - ema_slow

        for i in range(lookback, len(diff)):
            # Check if crossover occurred in the last N periods
            # A crossover means diff changed from negative to positive
            recent_diffs = diff[i - lookback:i + 1]

            # Check if there was a sign change from negative to positive
            for j in range(1, len(recent_diffs)):
                if recent_diffs[j - 1] < 0 and recent_diffs[j] > 0:
                    signals[i] = True
                    break

        return signals

    def check_bullish_crossover(self, ema_fast: float, ema_slow: float,
                                prev_ema_fast: float, prev_ema_slow: float) -> bool:
        """
        Check if a bullish crossover occurred (fast crossed above slow).

        Args:
            ema_fast: Current fast EMA
            ema_slow: Current slow EMA
            prev_ema_fast: Previous fast EMA
            prev_ema_slow: Previous slow EMA

        Returns:
            True if bullish crossover occurred
        """
        # Previous: fast was below slow
        # Current: fast is above slow
        return (prev_ema_fast < prev_ema_slow) and (ema_fast > ema_slow)

    def check_bearish_crossover(self, ema_fast: float, ema_slow: float,
                               prev_ema_fast: float, prev_ema_slow: float) -> bool:
        """
        Check if a bearish crossover occurred (slow crossed above fast).

        Args:
            ema_fast: Current fast EMA
            ema_slow: Current slow EMA
            prev_ema_fast: Previous fast EMA
            prev_ema_slow: Previous slow EMA

        Returns:
            True if bearish crossover occurred
        """
        # Previous: fast was above slow
        # Current: fast is below slow
        return (prev_ema_fast > prev_ema_slow) and (ema_fast < ema_slow)

    def get_latest_indicators(self, indicators: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Get the most recent indicator values.

        Args:
            indicators: List of indicator dictionaries

        Returns:
            Latest indicator dictionary or None
        """
        if not indicators:
            return None

        # Sort by date and return the latest
        sorted_indicators = sorted(indicators, key=lambda x: x['date'])
        return sorted_indicators[-1]

    def has_sufficient_history(self, daily_candles: List[Dict[str, Any]]) -> bool:
        """
        Check if there's sufficient historical data for indicator calculation.

        Args:
            daily_candles: List of daily candle dictionaries

        Returns:
            True if sufficient data is available
        """
        min_required = max(self.ema_slow, self.rsi_period, self.atr_period)
        return len(daily_candles) >= min_required

    def calculate_ema(self, values: List[float], period: int) -> List[float]:
        """
        Calculate Exponential Moving Average.

        Args:
            values: List of price values
            period: EMA period

        Returns:
            List of EMA values
        """
        if not values or len(values) < period:
            return []

        series = pd.Series(values)
        ema = ta.ema(series, length=period)

        return ema.tolist()

    def calculate_rsi(self, values: List[float], period: int = 14) -> List[float]:
        """
        Calculate Relative Strength Index.

        Args:
            values: List of price values
            period: RSI period

        Returns:
            List of RSI values
        """
        if not values or len(values) < period + 1:
            return []

        series = pd.Series(values)
        rsi = ta.rsi(series, length=period)

        return rsi.tolist()

    def calculate_atr(self, high: List[float], low: List[float],
                     close: List[float], period: int = 10) -> List[float]:
        """
        Calculate Average True Range.

        Args:
            high: List of high prices
            low: List of low prices
            close: List of close prices
            period: ATR period

        Returns:
            List of ATR values
        """
        if not high or not low or not close or len(high) < period + 1:
            return []

        high_series = pd.Series(high)
        low_series = pd.Series(low)
        close_series = pd.Series(close)

        atr = ta.atr(high_series, low_series, close_series, length=period)

        return atr.tolist()

    def detect_crossover_in_window(self, indicators: List[Dict[str, Any]],
                                   window: int = 5) -> bool:
        """
        Detect if EMA crossover occurred within the last N candles.

        Args:
            indicators: List of indicator dictionaries (sorted by date)
            window: Number of candles to look back

        Returns:
            True if crossover detected
        """
        if len(indicators) < 2:
            return False

        # Look at the last 'window' indicators
        recent_indicators = indicators[-window:] if len(indicators) >= window else indicators

        # Check for crossover in this window
        for i in range(1, len(recent_indicators)):
            prev = recent_indicators[i - 1]
            curr = recent_indicators[i]

            if prev.get('ema_12') and prev.get('ema_48') and curr.get('ema_12') and curr.get('ema_48'):
                if self.check_bullish_crossover(
                    curr['ema_12'], curr['ema_48'],
                    prev['ema_12'], prev['ema_48']
                ):
                    return True

        return False
