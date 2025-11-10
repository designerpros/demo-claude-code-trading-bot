"""
Data aggregation module for converting 15-minute candles to daily candles.
"""

import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


class CandleAggregator:
    """Aggregates 15-minute OHLCV data into daily candles."""

    @staticmethod
    def aggregate_to_daily(ohlcv_data: List[Dict[str, Any]], asset: str) -> List[Dict[str, Any]]:
        """
        Aggregate 15-minute candles into daily candles.

        Args:
            ohlcv_data: List of 15-minute OHLCV dictionaries
            asset: Asset symbol

        Returns:
            List of daily candle dictionaries
        """
        if not ohlcv_data:
            return []

        # Convert to DataFrame for easier aggregation
        df = pd.DataFrame(ohlcv_data)

        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Set timestamp as index
        df.set_index('timestamp', inplace=True)

        # Sort by timestamp
        df.sort_index(inplace=True)

        # Resample to daily
        daily = df.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })

        # Remove rows with NaN (incomplete days)
        daily = daily.dropna()

        # Convert back to list of dictionaries
        daily_candles = []
        for date_index, row in daily.iterrows():
            daily_candles.append({
                'date': date_index.date(),
                'asset': asset,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume'])
            })

        logger.debug(f"Aggregated {len(ohlcv_data)} 15m candles into {len(daily_candles)} daily candles for {asset}")

        return daily_candles

    @staticmethod
    def aggregate_multiple_assets(ohlcv_data_by_asset: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate 15-minute candles for multiple assets.

        Args:
            ohlcv_data_by_asset: Dictionary mapping asset symbols to their OHLCV data

        Returns:
            Dictionary mapping asset symbols to their daily candles
        """
        daily_candles_by_asset = {}

        for asset, ohlcv_data in ohlcv_data_by_asset.items():
            try:
                daily_candles = CandleAggregator.aggregate_to_daily(ohlcv_data, asset)
                if daily_candles:
                    daily_candles_by_asset[asset] = daily_candles
                    logger.info(f"Aggregated {asset}: {len(daily_candles)} daily candles")
            except Exception as e:
                logger.error(f"Error aggregating {asset}: {e}")
                continue

        return daily_candles_by_asset

    @staticmethod
    def get_latest_complete_day(ohlcv_data: List[Dict[str, Any]]) -> date:
        """
        Get the date of the latest complete day from 15-minute data.

        Args:
            ohlcv_data: List of 15-minute OHLCV dictionaries

        Returns:
            Date of the latest complete day
        """
        if not ohlcv_data:
            return None

        # Get the latest timestamp
        latest_timestamp = max(d['timestamp'] for d in ohlcv_data)

        if isinstance(latest_timestamp, str):
            latest_timestamp = datetime.fromisoformat(latest_timestamp)

        # If it's past midnight, the previous day is complete
        # Otherwise, go back 2 days
        today = latest_timestamp.date()
        yesterday = today - timedelta(days=1)

        return yesterday

    @staticmethod
    def check_data_completeness(ohlcv_data: List[Dict[str, Any]], expected_candles_per_day: int = 96) -> Dict[date, int]:
        """
        Check completeness of 15-minute data (should be 96 candles per day).

        Args:
            ohlcv_data: List of 15-minute OHLCV dictionaries
            expected_candles_per_day: Expected number of 15-minute candles in a day (default 96)

        Returns:
            Dictionary mapping dates to candle counts
        """
        if not ohlcv_data:
            return {}

        df = pd.DataFrame(ohlcv_data)

        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Extract date
        df['date'] = df['timestamp'].dt.date

        # Count candles per day
        candle_counts = df.groupby('date').size().to_dict()

        # Check for incomplete days
        incomplete_days = {d: count for d, count in candle_counts.items() if count < expected_candles_per_day}

        if incomplete_days:
            logger.warning(f"Found {len(incomplete_days)} incomplete days: {incomplete_days}")

        return candle_counts

    @staticmethod
    def merge_ohlcv_from_sources(ohlcv_sources: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Merge OHLCV data from multiple sources, preferring data with higher completeness.

        Args:
            ohlcv_sources: List of OHLCV data lists from different sources

        Returns:
            Merged OHLCV data
        """
        if not ohlcv_sources:
            return []

        # Filter out empty sources
        ohlcv_sources = [s for s in ohlcv_sources if s]

        if not ohlcv_sources:
            return []

        # If only one source, return it
        if len(ohlcv_sources) == 1:
            return ohlcv_sources[0]

        # Convert all sources to DataFrames
        dfs = []
        for source_data in ohlcv_sources:
            df = pd.DataFrame(source_data)
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['timestamp'] = df['timestamp'].dt.floor('T')  # Round to minute
            dfs.append(df)

        # Merge on timestamp, preferring the first source
        merged_df = dfs[0]

        for df in dfs[1:]:
            # Add missing timestamps from other sources
            missing_timestamps = ~df['timestamp'].isin(merged_df['timestamp'])
            merged_df = pd.concat([merged_df, df[missing_timestamps]], ignore_index=True)

        # Sort by timestamp
        merged_df.sort_values('timestamp', inplace=True)

        # Convert back to list of dictionaries
        merged_data = merged_df.to_dict('records')

        logger.info(f"Merged {len(ohlcv_sources)} sources into {len(merged_data)} candles")

        return merged_data
