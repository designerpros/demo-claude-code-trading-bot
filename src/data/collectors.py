"""
Data collection module for fetching cryptocurrency data from multiple sources.
Provides redundancy by pulling data from CoinGecko, Binance, and CoinCap.
"""

import requests
import ccxt
from pycoingecko import CoinGeckoAPI
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects cryptocurrency data from multiple sources with redundancy."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize data collectors.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.sources = config.get('sources', ['coingecko', 'binance', 'coincap'])

        # Initialize API clients
        self.coingecko = CoinGeckoAPI()
        self.binance = ccxt.binance({'enableRateLimit': True})
        self.coincap_base_url = "https://api.coincap.io/v2"

        # Stablecoin list
        self.stablecoins = {
            'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'USDD',
            'FRAX', 'USDN', 'GUSD', 'LUSD', 'SUSD', 'USDX', 'USDK',
            'USTC', 'UST', 'TRIBE', 'FEI', 'HUSD'
        }

    # ==================== Asset Selection ====================

    def get_top_assets(self, count: int = 100, exclude_stablecoins: bool = True) -> List[Dict[str, Any]]:
        """
        Get top N assets by volume and market cap.

        Args:
            count: Number of assets to return
            exclude_stablecoins: Whether to exclude stablecoins

        Returns:
            List of asset dictionaries with symbol, name, market_cap, volume, rank
        """
        assets = []

        # Try CoinGecko first (most reliable for rankings)
        try:
            assets = self._get_top_assets_coingecko(count * 2, exclude_stablecoins)
            if len(assets) >= count:
                logger.info(f"Retrieved {len(assets)} assets from CoinGecko")
                return assets[:count]
        except Exception as e:
            logger.warning(f"CoinGecko failed for top assets: {e}")

        # Fallback to Binance
        if not assets:
            try:
                assets = self._get_top_assets_binance(count * 2, exclude_stablecoins)
                if len(assets) >= count:
                    logger.info(f"Retrieved {len(assets)} assets from Binance")
                    return assets[:count]
            except Exception as e:
                logger.warning(f"Binance failed for top assets: {e}")

        # Fallback to CoinCap
        if not assets:
            try:
                assets = self._get_top_assets_coincap(count * 2, exclude_stablecoins)
                logger.info(f"Retrieved {len(assets)} assets from CoinCap")
            except Exception as e:
                logger.error(f"CoinCap failed for top assets: {e}")

        return assets[:count]

    def _get_top_assets_coingecko(self, count: int, exclude_stablecoins: bool) -> List[Dict[str, Any]]:
        """Get top assets from CoinGecko."""
        # Get market data
        markets = self.coingecko.get_coins_markets(
            vs_currency='usd',
            order='volume_desc',
            per_page=count,
            sparkline=False
        )

        assets = []
        for idx, coin in enumerate(markets, 1):
            symbol = coin['symbol'].upper()

            # Skip stablecoins if needed
            if exclude_stablecoins and symbol in self.stablecoins:
                continue

            assets.append({
                'symbol': symbol,
                'name': coin['name'],
                'market_cap': coin.get('market_cap', 0),
                'volume_24h': coin.get('total_volume', 0),
                'rank': idx,
                'is_stablecoin': symbol in self.stablecoins
            })

        # Sort by volume (primary) and market cap (secondary)
        assets.sort(key=lambda x: (x['volume_24h'], x['market_cap']), reverse=True)

        # Reassign ranks after sorting
        for idx, asset in enumerate(assets, 1):
            asset['rank'] = idx

        return assets

    def _get_top_assets_binance(self, count: int, exclude_stablecoins: bool) -> List[Dict[str, Any]]:
        """Get top assets from Binance."""
        # Get 24h ticker data
        tickers = self.binance.fetch_tickers()

        # Filter USDT pairs
        usdt_pairs = {k: v for k, v in tickers.items() if k.endswith('/USDT')}

        # Convert to list and sort by volume
        asset_list = []
        for symbol, ticker in usdt_pairs.items():
            base = symbol.split('/')[0]

            if exclude_stablecoins and base in self.stablecoins:
                continue

            asset_list.append({
                'symbol': base,
                'name': base,
                'volume_24h': ticker.get('quoteVolume', 0),
                'market_cap': 0,  # Binance doesn't provide market cap
                'rank': 0,
                'is_stablecoin': base in self.stablecoins
            })

        # Sort by volume
        asset_list.sort(key=lambda x: x['volume_24h'], reverse=True)

        # Assign ranks
        for idx, asset in enumerate(asset_list[:count], 1):
            asset['rank'] = idx

        return asset_list[:count]

    def _get_top_assets_coincap(self, count: int, exclude_stablecoins: bool) -> List[Dict[str, Any]]:
        """Get top assets from CoinCap."""
        url = f"{self.coincap_base_url}/assets"
        params = {'limit': count}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()['data']

        assets = []
        for idx, asset in enumerate(data, 1):
            symbol = asset['symbol'].upper()

            if exclude_stablecoins and symbol in self.stablecoins:
                continue

            assets.append({
                'symbol': symbol,
                'name': asset['name'],
                'market_cap': float(asset.get('marketCapUsd', 0)),
                'volume_24h': float(asset.get('volumeUsd24Hr', 0)),
                'rank': idx,
                'is_stablecoin': symbol in self.stablecoins
            })

        # Sort by volume (primary) and market cap (secondary)
        assets.sort(key=lambda x: (x['volume_24h'], x['market_cap']), reverse=True)

        # Reassign ranks
        for idx, asset in enumerate(assets, 1):
            asset['rank'] = idx

        return assets

    # ==================== OHLCV Data Collection ====================

    def fetch_ohlcv(self, symbol: str, interval: str = '15m',
                    since: Optional[datetime] = None,
                    limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV data with redundancy across sources.

        Args:
            symbol: Asset symbol
            interval: Candle interval (e.g., '15m', '1h', '1d')
            since: Start time for historical data
            limit: Maximum number of candles

        Returns:
            List of OHLCV dictionaries with source information
        """
        data = []

        # Try each source in order
        for source in self.sources:
            try:
                if source == 'binance':
                    data = self._fetch_ohlcv_binance(symbol, interval, since, limit)
                elif source == 'coingecko':
                    data = self._fetch_ohlcv_coingecko(symbol, interval, since, limit)
                elif source == 'coincap':
                    data = self._fetch_ohlcv_coincap(symbol, interval, since, limit)

                if data:
                    logger.debug(f"Fetched {len(data)} candles for {symbol} from {source}")
                    return data

            except Exception as e:
                logger.warning(f"Failed to fetch {symbol} from {source}: {e}")
                continue

        logger.error(f"Failed to fetch OHLCV data for {symbol} from all sources")
        return []

    def _fetch_ohlcv_binance(self, symbol: str, interval: str,
                             since: Optional[datetime], limit: int) -> List[Dict[str, Any]]:
        """Fetch OHLCV from Binance with pagination support for large requests."""
        # Convert interval format
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d'
        }
        binance_interval = interval_map.get(interval, '15m')

        # Prepare parameters
        pair = f"{symbol}/USDT"
        since_ms = int(since.timestamp() * 1000) if since else None

        # Binance has a max limit of 1000 candles per request
        # For larger requests, we need to paginate
        max_per_request = 1000
        all_ohlcv = []

        if limit > max_per_request:
            # Paginate through multiple requests
            current_since = since_ms
            remaining = limit

            while remaining > 0:
                fetch_limit = min(remaining, max_per_request)
                batch = self.binance.fetch_ohlcv(pair, binance_interval, current_since, fetch_limit)

                if not batch:
                    break

                all_ohlcv.extend(batch)
                remaining -= len(batch)

                # Update since to last candle's timestamp + 1ms
                if len(batch) > 0:
                    current_since = batch[-1][0] + 1
                else:
                    break

                # If we got fewer candles than requested, we've reached the end
                if len(batch) < fetch_limit:
                    break

                time.sleep(0.1)  # Rate limiting between requests

            ohlcv = all_ohlcv
        else:
            # Single request
            ohlcv = self.binance.fetch_ohlcv(pair, binance_interval, since_ms, limit)

        # Convert to our format
        data = []
        for candle in ohlcv:
            data.append({
                'timestamp': datetime.fromtimestamp(candle[0] / 1000),
                'asset': symbol,
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5],
                'interval': interval,
                'source': 'binance'
            })

        return data

    def _fetch_ohlcv_coingecko(self, symbol: str, interval: str,
                               since: Optional[datetime], limit: int) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV from CoinGecko.
        Note: CoinGecko only provides daily data for free tier.
        """
        # Get coin ID from symbol
        try:
            coins_list = self.coingecko.get_coins_list()
            coin_id = None
            for coin in coins_list:
                if coin['symbol'].upper() == symbol.upper():
                    coin_id = coin['id']
                    break

            if not coin_id:
                logger.warning(f"Could not find CoinGecko ID for {symbol}")
                return []

            # Calculate days
            days = limit if interval == '1d' else 30

            # Fetch market chart
            market_data = self.coingecko.get_coin_market_chart_by_id(
                id=coin_id,
                vs_currency='usd',
                days=days
            )

            # Convert to OHLCV format (CoinGecko only provides prices)
            # We'll use price as all OHLC values (approximation)
            prices = market_data['prices']
            volumes = market_data['total_volumes']

            data = []
            for i, (timestamp_ms, price) in enumerate(prices):
                if i < len(volumes):
                    volume = volumes[i][1]
                else:
                    volume = 0

                data.append({
                    'timestamp': datetime.fromtimestamp(timestamp_ms / 1000),
                    'asset': symbol,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume,
                    'interval': interval,
                    'source': 'coingecko'
                })

            return data

        except Exception as e:
            logger.warning(f"CoinGecko OHLCV fetch failed for {symbol}: {e}")
            return []

    def _fetch_ohlcv_coincap(self, symbol: str, interval: str,
                            since: Optional[datetime], limit: int) -> List[Dict[str, Any]]:
        """Fetch OHLCV from CoinCap."""
        # Convert interval format
        interval_map = {
            '1m': 'm1', '5m': 'm5', '15m': 'm15', '30m': 'm30',
            '1h': 'h1', '4h': 'h4', '1d': 'd1'
        }
        coincap_interval = interval_map.get(interval, 'm15')

        # Get asset ID
        url = f"{self.coincap_base_url}/assets"
        response = requests.get(url, params={'search': symbol}, timeout=10)
        assets = response.json()['data']

        if not assets:
            return []

        asset_id = assets[0]['id']

        # Fetch candles
        url = f"{self.coincap_base_url}/assets/{asset_id}/history"
        params = {
            'interval': coincap_interval,
        }

        if since:
            params['start'] = int(since.timestamp() * 1000)

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        candles = response.json()['data']

        # CoinCap only provides price, not OHLCV
        # We'll approximate OHLCV from price data
        data = []
        for candle in candles[:limit]:
            price = float(candle['priceUsd'])
            data.append({
                'timestamp': datetime.fromtimestamp(candle['time'] / 1000),
                'asset': symbol,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': 0,  # CoinCap history doesn't include volume
                'interval': interval,
                'source': 'coincap'
            })

        return data

    # ==================== Historical Data Bootstrap ====================

    def fetch_historical_data(self, symbols: List[str], days: int = 48,
                             interval: str = '15m') -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch historical data for multiple symbols.

        Args:
            symbols: List of asset symbols
            days: Number of days of historical data
            interval: Candle interval

        Returns:
            Dictionary mapping symbols to their OHLCV data
        """
        since = datetime.now() - timedelta(days=days)
        historical_data = {}

        for symbol in symbols:
            logger.info(f"Fetching {days} days of historical data for {symbol}")

            try:
                data = self.fetch_ohlcv(symbol, interval, since)
                if data:
                    historical_data[symbol] = data
                    logger.info(f"Successfully fetched {len(data)} candles for {symbol}")
                else:
                    logger.warning(f"No data retrieved for {symbol}")

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching historical data for {symbol}: {e}")
                continue

        return historical_data

    # ==================== Latest Price ====================

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for an asset."""
        for source in self.sources:
            try:
                if source == 'binance':
                    ticker = self.binance.fetch_ticker(f"{symbol}/USDT")
                    return ticker['last']
                elif source == 'coingecko':
                    # Get coin ID
                    coins_list = self.coingecko.get_coins_list()
                    coin_id = None
                    for coin in coins_list:
                        if coin['symbol'].upper() == symbol.upper():
                            coin_id = coin['id']
                            break
                    if coin_id:
                        price_data = self.coingecko.get_price(ids=coin_id, vs_currencies='usd')
                        return price_data[coin_id]['usd']
                elif source == 'coincap':
                    url = f"{self.coincap_base_url}/assets"
                    response = requests.get(url, params={'search': symbol}, timeout=10)
                    assets = response.json()['data']
                    if assets:
                        return float(assets[0]['priceUsd'])
            except Exception as e:
                logger.debug(f"Failed to get price for {symbol} from {source}: {e}")
                continue

        logger.warning(f"Could not get price for {symbol} from any source")
        return None
