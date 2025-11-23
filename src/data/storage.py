"""
Database storage layer for the trading bot.
Handles all database operations using PostgreSQL.
"""

import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class DatabaseStorage:
    """Handles all database operations for the trading bot."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize database connection.

        Args:
            config: Database configuration dictionary
        """
        self.config = config
        self.connection_params = {
            'host': config.get('host', 'localhost'),
            'port': config.get('port', 5432),
            'database': config.get('name', 'trading_bot'),
            'user': config.get('user', 'trading_bot_user'),
            'password': config.get('password', '')
        }

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def initialize_database(self, schema_file: str):
        """
        Initialize database with schema.

        Args:
            schema_file: Path to SQL schema file
        """
        try:
            with open(schema_file, 'r') as f:
                schema_sql = f.read()

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_sql)

            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    # ==================== Asset Operations ====================

    def upsert_assets(self, assets: List[Dict[str, Any]]):
        """
        Insert or update multiple assets.

        Args:
            assets: List of asset dictionaries
        """
        if not assets:
            return

        query = """
            INSERT INTO assets (symbol, name, market_cap, volume_24h, rank, is_stablecoin, is_tracked, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                name = EXCLUDED.name,
                market_cap = EXCLUDED.market_cap,
                volume_24h = EXCLUDED.volume_24h,
                rank = EXCLUDED.rank,
                is_stablecoin = EXCLUDED.is_stablecoin,
                is_tracked = EXCLUDED.is_tracked,
                last_updated = EXCLUDED.last_updated
        """

        data = [
            (
                a['symbol'],
                a.get('name', ''),
                a.get('market_cap', 0),
                a.get('volume_24h', 0),
                a.get('rank', 0),
                a.get('is_stablecoin', False),
                a.get('is_tracked', True),
                datetime.now()
            )
            for a in assets
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, query, data)

        logger.info(f"Upserted {len(assets)} assets")

    def get_tracked_assets(self) -> List[str]:
        """Get list of currently tracked asset symbols."""
        query = "SELECT symbol FROM assets WHERE is_tracked = TRUE ORDER BY rank"

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return [row[0] for row in cur.fetchall()]

    def update_asset_tracking(self, symbol: str, is_tracked: bool):
        """Update tracking status for an asset."""
        query = "UPDATE assets SET is_tracked = %s, last_updated = %s WHERE symbol = %s"

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (is_tracked, datetime.now(), symbol))

    # ==================== OHLCV Data Operations ====================

    def insert_ohlcv_data(self, data: List[Dict[str, Any]]):
        """
        Insert OHLCV data (15-minute candles).

        Args:
            data: List of OHLCV dictionaries
        """
        if not data:
            return

        query = """
            INSERT INTO ohlcv_data (timestamp, asset, open, high, low, close, volume, interval, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (timestamp, asset, interval, source) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """

        values = [
            (
                d['timestamp'],
                d['asset'],
                d['open'],
                d['high'],
                d['low'],
                d['close'],
                d['volume'],
                d.get('interval', '15m'),
                d.get('source', 'unknown')
            )
            for d in data
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, query, values)

        logger.debug(f"Inserted {len(data)} OHLCV records")

    def get_ohlcv_data(self, asset: str, start_time: datetime, end_time: datetime,
                       interval: str = '15m') -> List[Dict[str, Any]]:
        """Get OHLCV data for an asset within a time range."""
        query = """
            SELECT timestamp, asset, open, high, low, close, volume, source
            FROM ohlcv_data
            WHERE asset = %s AND interval = %s AND timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp
        """

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (asset, interval, start_time, end_time))
                return [dict(row) for row in cur.fetchall()]

    # ==================== Daily Candles Operations ====================

    def insert_daily_candles(self, candles: List[Dict[str, Any]]):
        """
        Insert daily candles (aggregated from 15m data).

        Args:
            candles: List of daily candle dictionaries
        """
        if not candles:
            return

        query = """
            INSERT INTO daily_candles (date, asset, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, asset) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """

        values = [
            (
                c['date'],
                c['asset'],
                c['open'],
                c['high'],
                c['low'],
                c['close'],
                c['volume']
            )
            for c in candles
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, query, values)

        logger.debug(f"Inserted {len(candles)} daily candles")

    def get_daily_candles(self, asset: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get daily candles for an asset within a date range."""
        query = """
            SELECT date, asset, open, high, low, close, volume
            FROM daily_candles
            WHERE asset = %s AND date >= %s AND date <= %s
            ORDER BY date
        """

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (asset, start_date, end_date))
                return [dict(row) for row in cur.fetchall()]

    def get_latest_daily_candle_date(self, asset: str) -> Optional[date]:
        """Get the date of the latest daily candle for an asset."""
        query = "SELECT MAX(date) FROM daily_candles WHERE asset = %s"

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (asset,))
                result = cur.fetchone()
                return result[0] if result and result[0] else None

    # ==================== Trade Operations ====================

    def insert_trade(self, trade: Dict[str, Any]):
        """Insert a trade record."""
        query = """
            INSERT INTO trades (
                trade_id, asset, trade_type, timestamp, price, units, value, fee, fee_percentage,
                liquidity_before, liquidity_after, entry_trade_id, exit_trade_id,
                time_in_trade_hours, profit_loss, profit_loss_percentage, exit_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            trade['trade_id'],
            trade['asset'],
            trade['trade_type'],
            trade['timestamp'],
            trade['price'],
            trade['units'],
            trade['value'],
            trade['fee'],
            trade['fee_percentage'],
            trade.get('liquidity_before'),
            trade.get('liquidity_after'),
            trade.get('entry_trade_id'),
            trade.get('exit_trade_id'),
            trade.get('time_in_trade_hours'),
            trade.get('profit_loss'),
            trade.get('profit_loss_percentage'),
            trade.get('exit_reason')
        )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)

        logger.info(f"Inserted trade: {trade['trade_id']} - {trade['trade_type']} {trade['asset']}")

    def update_trade_exit_mapping(self, entry_trade_id: str, exit_trade_id: str):
        """Map an entry trade to its exit trade."""
        query = "UPDATE trades SET exit_trade_id = %s WHERE trade_id = %s"

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (exit_trade_id, entry_trade_id))

    def get_all_trades(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all trades, optionally limited."""
        query = "SELECT * FROM trades ORDER BY timestamp DESC"
        params = ()

        if limit:
            query += " LIMIT %s"
            params = (limit,)

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]

    # ==================== Position Operations ====================

    def insert_position(self, position: Dict[str, Any]):
        """Insert a new position."""
        query = """
            INSERT INTO positions (
                asset, entry_trade_id, units, entry_price, entry_time,
                current_price, current_value, highest_value, unrealized_pnl,
                unrealized_pnl_percentage, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            position['asset'],
            position['entry_trade_id'],
            position['units'],
            position['entry_price'],
            position['entry_time'],
            position.get('current_price', position['entry_price']),
            position.get('current_value', position['units'] * position['entry_price']),
            position.get('highest_value', position['units'] * position['entry_price']),
            position.get('unrealized_pnl', 0),
            position.get('unrealized_pnl_percentage', 0),
            position.get('status', 'OPEN')
        )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)

        logger.info(f"Inserted position: {position['asset']}")

    def update_position(self, asset: str, updates: Dict[str, Any]):
        """Update an open position."""
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        set_clause += ", updated_at = %s"
        query = f"UPDATE positions SET {set_clause} WHERE asset = %s AND status = 'OPEN'"

        values = list(updates.values()) + [datetime.now(), asset]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)

    def close_position(self, asset: str):
        """Close a position."""
        query = "UPDATE positions SET status = 'CLOSED', updated_at = %s WHERE asset = %s AND status = 'OPEN'"

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (datetime.now(), asset))

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        query = "SELECT * FROM positions WHERE status = 'OPEN' ORDER BY entry_time"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return [dict(row) for row in cur.fetchall()]

    def get_position(self, asset: str) -> Optional[Dict[str, Any]]:
        """Get an open position for a specific asset."""
        query = "SELECT * FROM positions WHERE asset = %s AND status = 'OPEN'"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (asset,))
                result = cur.fetchone()
                return dict(result) if result else None

    # ==================== Portfolio Operations ====================

    def insert_portfolio_snapshot(self, snapshot: Dict[str, Any]):
        """Insert a portfolio snapshot."""
        query = """
            INSERT INTO portfolio_snapshots (
                timestamp, total_value, cash, positions_value, cash_percentage,
                positions_percentage, num_positions, daily_pnl, daily_pnl_percentage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (timestamp) DO UPDATE SET
                total_value = EXCLUDED.total_value,
                cash = EXCLUDED.cash,
                positions_value = EXCLUDED.positions_value,
                cash_percentage = EXCLUDED.cash_percentage,
                positions_percentage = EXCLUDED.positions_percentage,
                num_positions = EXCLUDED.num_positions,
                daily_pnl = EXCLUDED.daily_pnl,
                daily_pnl_percentage = EXCLUDED.daily_pnl_percentage
        """

        values = (
            snapshot['timestamp'],
            snapshot['total_value'],
            snapshot['cash'],
            snapshot['positions_value'],
            snapshot['cash_percentage'],
            snapshot['positions_percentage'],
            snapshot['num_positions'],
            snapshot.get('daily_pnl'),
            snapshot.get('daily_pnl_percentage')
        )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)

    def get_latest_portfolio_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get the most recent portfolio snapshot."""
        query = "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                result = cur.fetchone()
                return dict(result) if result else None

    def get_portfolio_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get portfolio history for the last N days."""
        query = """
            SELECT * FROM portfolio_snapshots
            WHERE timestamp >= NOW() - INTERVAL '%s days'
            ORDER BY timestamp
        """

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (days,))
                return [dict(row) for row in cur.fetchall()]

    # ==================== Indicator Operations ====================

    def insert_indicators(self, indicators: List[Dict[str, Any]]):
        """Insert calculated indicators."""
        if not indicators:
            return

        query = """
            INSERT INTO indicators (
                date, asset, ema_12, ema_48, rsi_14, atr_10, price_change,
                ema_crossover_signal, rsi_oversold, atr_breakout
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, asset) DO UPDATE SET
                ema_12 = EXCLUDED.ema_12,
                ema_48 = EXCLUDED.ema_48,
                rsi_14 = EXCLUDED.rsi_14,
                atr_10 = EXCLUDED.atr_10,
                price_change = EXCLUDED.price_change,
                ema_crossover_signal = EXCLUDED.ema_crossover_signal,
                rsi_oversold = EXCLUDED.rsi_oversold,
                atr_breakout = EXCLUDED.atr_breakout
        """

        values = [
            (
                i['date'],
                i['asset'],
                i.get('ema_12'),
                i.get('ema_48'),
                i.get('rsi_14'),
                i.get('atr_10'),
                i.get('price_change'),
                i.get('ema_crossover_signal', False),
                i.get('rsi_oversold', False),
                i.get('atr_breakout', False)
            )
            for i in indicators
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, query, values)

    def get_latest_indicators(self, asset: str, days: int = 60) -> List[Dict[str, Any]]:
        """Get latest indicators for an asset."""
        query = """
            SELECT * FROM indicators
            WHERE asset = %s
            ORDER BY date DESC
            LIMIT %s
        """

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (asset, days))
                return [dict(row) for row in cur.fetchall()]

    # ==================== System Log Operations ====================

    def log_system_event(self, level: str, module: str, message: str, details: Optional[Dict] = None):
        """Log a system event."""
        query = """
            INSERT INTO system_logs (level, module, message, details)
            VALUES (%s, %s, %s, %s)
        """

        import json
        details_json = json.dumps(details) if details else None

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (level, module, message, details_json))

    def get_system_logs(self, level: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get system logs."""
        if level:
            query = "SELECT * FROM system_logs WHERE level = %s ORDER BY timestamp DESC LIMIT %s"
            params = (level, limit)
        else:
            query = "SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT %s"
            params = (limit,)

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
