CREATE TABLE IF NOT EXISTS symbols (
    symbol     TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    sector     TEXT NOT NULL,
    added_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_prices (
    symbol     TEXT NOT NULL REFERENCES symbols (symbol),
    trade_date TEXT NOT NULL,
    open       REAL NOT NULL CHECK (open > 0),
    high       REAL NOT NULL CHECK (high > 0),
    low        REAL NOT NULL CHECK (low > 0),
    close      REAL NOT NULL CHECK (close > 0),
    adj_close  REAL NOT NULL CHECK (adj_close > 0),
    volume     INTEGER NOT NULL CHECK (volume >= 0),
    loaded_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date),
    CHECK (high >= low)
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices (trade_date);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    message     TEXT
);
