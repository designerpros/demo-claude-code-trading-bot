-- Trading Bot Database Schema

-- Assets table: Track all crypto assets
CREATE TABLE IF NOT EXISTS assets (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    market_cap DECIMAL(30, 2),
    volume_24h DECIMAL(30, 2),
    rank INTEGER,
    is_stablecoin BOOLEAN DEFAULT FALSE,
    is_tracked BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OHLCV data table: Store 15-minute candles
CREATE TABLE IF NOT EXISTS ohlcv_data (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    asset VARCHAR(20) NOT NULL REFERENCES assets(symbol),
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,
    interval VARCHAR(10) DEFAULT '15m',
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, asset, interval, source)
);

CREATE INDEX idx_ohlcv_timestamp ON ohlcv_data(timestamp);
CREATE INDEX idx_ohlcv_asset ON ohlcv_data(asset);
CREATE INDEX idx_ohlcv_asset_timestamp ON ohlcv_data(asset, timestamp);

-- Daily candles table: Aggregated from 15m data
CREATE TABLE IF NOT EXISTS daily_candles (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    asset VARCHAR(20) NOT NULL REFERENCES assets(symbol),
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, asset)
);

CREATE INDEX idx_daily_date ON daily_candles(date);
CREATE INDEX idx_daily_asset ON daily_candles(asset);
CREATE INDEX idx_daily_asset_date ON daily_candles(asset, date);

-- Trades table: Log all trades with unique IDs
CREATE TABLE IF NOT EXISTS trades (
    trade_id VARCHAR(50) PRIMARY KEY,
    asset VARCHAR(20) NOT NULL REFERENCES assets(symbol),
    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('ENTRY', 'EXIT')),
    timestamp TIMESTAMP NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    units DECIMAL(20, 8) NOT NULL,
    value DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) NOT NULL,
    fee_percentage DECIMAL(5, 4) NOT NULL,
    liquidity_before DECIMAL(20, 8),
    liquidity_after DECIMAL(20, 8),
    entry_trade_id VARCHAR(50),
    exit_trade_id VARCHAR(50),
    time_in_trade_hours DECIMAL(10, 2),
    profit_loss DECIMAL(20, 8),
    profit_loss_percentage DECIMAL(10, 4),
    exit_reason VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_asset ON trades(asset);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);
CREATE INDEX idx_trades_type ON trades(trade_type);
CREATE INDEX idx_trades_entry_id ON trades(entry_trade_id);

-- Positions table: Track active positions
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    asset VARCHAR(20) NOT NULL REFERENCES assets(symbol),
    entry_trade_id VARCHAR(50) NOT NULL REFERENCES trades(trade_id),
    units DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    current_price DECIMAL(20, 8),
    current_value DECIMAL(20, 8),
    highest_value DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    unrealized_pnl_percentage DECIMAL(10, 4),
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset, status, entry_trade_id)
);

CREATE INDEX idx_positions_asset ON positions(asset);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_entry_trade ON positions(entry_trade_id);

-- Portfolio snapshots table: Daily portfolio state
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL UNIQUE,
    total_value DECIMAL(20, 8) NOT NULL,
    cash DECIMAL(20, 8) NOT NULL,
    positions_value DECIMAL(20, 8) NOT NULL,
    cash_percentage DECIMAL(5, 2) NOT NULL,
    positions_percentage DECIMAL(5, 2) NOT NULL,
    num_positions INTEGER DEFAULT 0,
    daily_pnl DECIMAL(20, 8),
    daily_pnl_percentage DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_timestamp ON portfolio_snapshots(timestamp);

-- Indicators table: Store calculated indicators for each asset/day
CREATE TABLE IF NOT EXISTS indicators (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    asset VARCHAR(20) NOT NULL REFERENCES assets(symbol),
    ema_12 DECIMAL(20, 8),
    ema_48 DECIMAL(20, 8),
    rsi_14 DECIMAL(10, 4),
    atr_10 DECIMAL(20, 8),
    price_change DECIMAL(20, 8),
    ema_crossover_signal BOOLEAN DEFAULT FALSE,
    rsi_oversold BOOLEAN DEFAULT FALSE,
    atr_breakout BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, asset)
);

CREATE INDEX idx_indicators_date ON indicators(date);
CREATE INDEX idx_indicators_asset ON indicators(asset);
CREATE INDEX idx_indicators_asset_date ON indicators(asset, date);

-- System log table: Track bot operations
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(20) NOT NULL,
    module VARCHAR(100),
    message TEXT NOT NULL,
    details JSONB
);

CREATE INDEX idx_logs_timestamp ON system_logs(timestamp);
CREATE INDEX idx_logs_level ON system_logs(level);
